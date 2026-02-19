# src/optimize_detection_parameters.py
"""
Optimize water-detection parameters for flood mapping.

Searches over percentile, VV/VH thresholds, and small-object size to maximize
F1-score and IoU against a reference shapefile (e.g. EMS). Run from project root:

    python src/optimize_detection_parameters.py

Copy the printed best detect_kwargs into config.yaml (under detect_kwargs or per scene).
"""
import os
import sys
import itertools

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
PRE_FILE = os.path.join(DATA_DIR, "may.tif")
POST_FILE = os.path.join(DATA_DIR, "june.tif")
DEM_FILE = os.path.join(DATA_DIR, "elevation.tif")
EMS_FILE = os.path.join(DATA_DIR, "EMSN_199.shp")
SLOPE_THRESH_DEG = 15

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preprocess
import detect_flood
import postprocess
import validation


def run_one(detect_kwargs, quiet=True):
    profile = preprocess.preprocess_images(
        PRE_FILE, POST_FILE, output_dir=RESULTS_DIR,
        dem_path=DEM_FILE, slope_thresh=SLOPE_THRESH_DEG,
        detect_kwargs=detect_kwargs,
    )
    detect_flood.change_detection(output_dir=RESULTS_DIR)
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
        "small_object_size": [1500, 2000],
    }
    keys = list(param_grid.keys())
    combos = list(itertools.product(*(param_grid[k] for k in keys)))
    print(f"Optimizing over {len(combos)} parameter combinations...")
    best_f1 = -1.0
    best_params = None
    best_iou = -1.0
    for i, combo in enumerate(combos):
        detect_kwargs = dict(zip(keys, combo))
        try:
            f1, iou = run_one(detect_kwargs, quiet=True)
        except Exception as e:
            print(f"  Skip {detect_kwargs}: {e}")
            continue
        if f1 > best_f1:
            best_f1 = f1
            best_iou = iou
            best_params = detect_kwargs.copy()
        print(f"  [{i+1}/{len(combos)}] {detect_kwargs} -> F1={f1:.3f}, IoU={iou:.3f}")
    print("\n--- Best parameters ---")
    print(f"F1={best_f1:.3f}, IoU={best_iou:.3f}")
    if best_params:
        print("detect_kwargs:", best_params, "\n(Add to config.yaml under detect_kwargs or per scene)")


if __name__ == "__main__":
    main()
