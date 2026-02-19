# src/run_pipeline.py
"""
Config-driven flood mapping pipeline. Add new images by editing config.yaml (scenes).
Run: python src/run_pipeline.py [--config config.yaml] [--scene SCENE_NAME]
"""
import os
import sys
import argparse

_script_dir = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(_script_dir)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

import preprocess
import detect_flood
import postprocess
import validation

def load_config(config_path):
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML required for config: pip install pyyaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def resolve_path(root, path):
    """path: relative to root or absolute. Return absolute path."""
    if path is None:
        return None
    p = path.replace("/", os.sep).replace("\\", os.sep)
    if os.path.isabs(p):
        return p
    return os.path.normpath(os.path.join(root, p))

def run_scene(scene, project_root, results_dir, defaults, results_flat=False):
    """Run full pipeline for one scene. Paths must be absolute."""
    name = scene.get("name", "default")
    pre_image = resolve_path(project_root, scene["pre_image"])
    post_image = resolve_path(project_root, scene["post_image"])
    output_dir = results_dir if results_flat else os.path.join(results_dir, name)
    os.makedirs(output_dir, exist_ok=True)

    dem_path = scene.get("dem") if scene.get("dem") is not None else defaults.get("default_dem")
    dem_path = resolve_path(project_root, dem_path) if dem_path else None
    reference_shp = scene.get("reference_shp") if scene.get("reference_shp") is not None else defaults.get("default_reference_shp")
    reference_shp = resolve_path(project_root, reference_shp) if reference_shp else None
    exclude_water = scene.get("exclude_permanent_water") if scene.get("exclude_permanent_water") is not None else defaults.get("exclude_permanent_water")
    exclude_water = resolve_path(project_root, exclude_water) if exclude_water else None

    use_dem = scene.get("use_dem", defaults.get("use_dem", False))
    slope_thresh = scene.get("slope_thresh_deg", defaults.get("slope_thresh_deg"))
    max_elevation_m = scene.get("max_elevation_m", defaults.get("max_elevation_m"))
    detect_kwargs = scene.get("detect_kwargs") or defaults.get("detect_kwargs") or {}
    flood_refine = scene.get("flood_refine", defaults.get("flood_refine", False))

    if not os.path.isfile(pre_image):
        raise FileNotFoundError(f"Pre image not found: {pre_image}")
    if not os.path.isfile(post_image):
        raise FileNotFoundError(f"Post image not found: {post_image}")

    print(f"\n--- Scene: {name} ---")
    preprocess_kw = dict(
        pre_path=pre_image, post_path=post_image, output_dir=output_dir,
        detect_kwargs=detect_kwargs,
    )
    if use_dem and dem_path and os.path.isfile(dem_path):
        preprocess_kw.update(dem_path=dem_path, slope_thresh=slope_thresh, max_elevation_m=max_elevation_m)
    profile = preprocess.preprocess_images(**preprocess_kw)

    detect_flood.change_detection(output_dir=output_dir, refine=flood_refine, exclude_water_path=exclude_water, profile=profile)
    postprocess.postprocess(output_dir=output_dir, profile=profile)
    metrics = validation.validate(output_dir=output_dir, ems_shp=reference_shp)
    good_f1 = defaults.get("good_f1_min", 0.60)
    good_iou = defaults.get("good_iou_min", 0.45)
    postprocess.write_summary(output_dir, profile=profile, metrics=metrics, good_f1_min=good_f1, good_iou_min=good_iou)
    print(f"Done: {output_dir}")
    return output_dir

def main():
    parser = argparse.ArgumentParser(description="Flood mapping pipeline (config-driven)")
    parser.add_argument("--config", default=None, help="Path to config.yaml (default: project_root/config.yaml)")
    parser.add_argument("--scene", default=None, help="Run only this scene name (default: all scenes)")
    args = parser.parse_args()

    config_path = args.config
    if config_path is None:
        config_path = os.path.join(PROJECT_ROOT, "config.yaml")
    config_path = os.path.normpath(os.path.abspath(config_path))
    if not os.path.isfile(config_path):
        print(f"Config not found: {config_path}")
        print("Create config.yaml from the example or run with --config path/to/config.yaml")
        sys.exit(1)

    config = load_config(config_path)
    root = config.get("project_root", ".")
    if not os.path.isabs(root):
        root = os.path.normpath(os.path.join(os.path.dirname(config_path), root))
    project_root = os.path.abspath(root)
    results_dir = resolve_path(project_root, config.get("results_dir", "results"))
    results_flat = config.get("results_flat", False)
    os.makedirs(results_dir, exist_ok=True)

    defaults = {
        "default_dem": config.get("default_dem"),
        "default_reference_shp": config.get("default_reference_shp"),
        "use_dem": config.get("use_dem", False),
        "slope_thresh_deg": config.get("slope_thresh_deg"),
        "max_elevation_m": config.get("max_elevation_m"),
        "detect_kwargs": config.get("detect_kwargs") or {},
        "flood_refine": config.get("flood_refine", False),
        "good_f1_min": config.get("good_f1_min", 0.60),
        "good_iou_min": config.get("good_iou_min", 0.45),
        "exclude_permanent_water": config.get("exclude_permanent_water"),
    }

    scenes = config.get("scenes", [])
    if not scenes:
        print("No scenes in config. Add entries under 'scenes' in config.yaml")
        sys.exit(1)

    if args.scene:
        scenes = [s for s in scenes if s.get("name") == args.scene]
        if not scenes:
            print(f"Scene '{args.scene}' not found in config.")
            sys.exit(1)

    for scene in scenes:
        run_scene(scene, project_root, results_dir, defaults, results_flat=results_flat)

    if len(scenes) >= 2 and not results_flat:
        import json
        print("\n" + "=" * 60 + "\nCOMPARISON\n" + "=" * 60)
        for scene in scenes:
            name = scene.get("name", "default")
            use_dem = scene.get("use_dem", defaults.get("use_dem", False))
            slope = scene.get("slope_thresh_deg", defaults.get("slope_thresh_deg"))
            dem_label = f"DEM {slope}°" if use_dem else "no DEM"
            path = os.path.join(results_dir, name, "summary.json")
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    s = json.load(f)
                print(f"  {name} ({dem_label}):  F1={s.get('f1', '-')}  IoU={s.get('iou', '-')}  ha={s.get('flood_area_ha', '-')}  {s.get('result_quality', '')}")
            else:
                print(f"  {name} ({dem_label}):  (no summary.json)")
        print("=" * 60)

    print("\nPipeline finished. Check the results folder(s).")

if __name__ == "__main__":
    main()
