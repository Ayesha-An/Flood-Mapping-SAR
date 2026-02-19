# src/optimize_detection_parameters.py
"""
Optimize water-detection and DSM slope parameters for flood mapping.

Searches over percentile, VV/VH thresholds, small_object_size, and slope_thresh_deg
to maximize F1-score and IoU against a reference shapefile (e.g. EMS). Run from project root:

    python src/optimize_detection_parameters.py

Copy the printed slope_thresh_deg and detect_kwargs into config.yaml.
"""
import os
import sys
import itertools

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
PRE_FILE = os.path.join(DATA_DIR, "may.tif")
POST_FILE = os.path.join(DATA_DIR, "june.tif")
DSM_FILE = os.path.join(DATA_DIR, "DSM.tif")  # DSM (e.g. InSAR Elevation VV)
EMS_FILE = os.path.join(DATA_DIR, "EMSN_199.shp")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preprocess
import detect_flood
import postprocess
import validation


def run_one(detect_kwargs, slope_thresh_deg, quiet=True):
    """Run pipeline with given detect_kwargs and slope_thresh_deg (DSM slope mask)."""
    use_dsm = os.path.isfile(DSM_FILE) and slope_thresh_deg is not None
    profile = preprocess.preprocess_images(
        PRE_FILE, POST_FILE, output_dir=RESULTS_DIR,
        dsm_path=DSM_FILE if use_dsm else None,
        slope_thresh=slope_thresh_deg if use_dsm else None,
        detect_kwargs=detect_kwargs,
    )
    detect_flood.change_detection(
        output_dir=RESULTS_DIR,
        slope_thresh=slope_thresh_deg if use_dsm else None,
    )
    postprocess.postprocess(output_dir=RESULTS_DIR, profile=profile)
    if quiet:
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            metrics = validation.validate(output_dir=RESULTS_DIR, ems_shp=EMS_FILE)
    else:
        metrics = validation.validate(output_dir=RESULTS_DIR, ems_shp=EMS_FILE)
    return metrics["f1"], metrics["iou"]


def main():
    param_grid = {
        "percentile": [88, 90, 92],
        "vv_thresh": [0.025, 0.03, 0.035],
        "vh_thresh": [0.008, 0.01, 0.012],
        "small_object_size": [1500, 2000]

    }
    keys = list(param_grid.keys())
    combos = list(itertools.product(*(param_grid[k] for k in keys)))
    print(f"Optimizing over {len(combos)} parameter combinations (including slope_thresh_deg)...")
    best_f1 = -1.0
    best_params = None
    best_slope = None
    best_iou = -1.0
    for i, combo in enumerate(combos):
        params = dict(zip(keys, combo))
        slope_thresh_deg = params.pop("slope_thresh_deg")
        detect_kwargs = params
        try:
            f1, iou = run_one(detect_kwargs, slope_thresh_deg=slope_thresh_deg, quiet=True)
        except Exception as e:
            print(f"  Skip detect_kwargs={detect_kwargs}, slope={slope_thresh_deg}°: {e}")
            continue
        if f1 > best_f1:
            best_f1 = f1
            best_iou = iou
            best_params = detect_kwargs.copy()
            best_slope = slope_thresh_deg
        print(f"  [{i+1}/{len(combos)}] slope={slope_thresh_deg}° {detect_kwargs} -> F1={f1:.3f}, IoU={iou:.3f}")
    print("\n--- Best parameters ---")
    print(f"F1={best_f1:.3f}, IoU={best_iou:.3f}")
    if best_params is not None:
        print("slope_thresh_deg:", best_slope)
        print("detect_kwargs:", best_params)
        print("(Add to config.yaml: slope_thresh_deg under scene/defaults, detect_kwargs under detect_kwargs or per scene)")


if __name__ == "__main__":
    main()
