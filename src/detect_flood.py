# src/detect_flood.py
import os
import numpy as np

def change_detection(output_dir="results"):
    """Optional: redundant since preprocess now saves flood_area"""
    pre_water = np.load(os.path.join(output_dir, "pre_water.npy"))
    post_water = np.load(os.path.join(output_dir, "post_water.npy"))

    flood_area = np.logical_and(post_water == 1, pre_water == 0).astype(np.uint8)
    np.save(os.path.join(output_dir, "flood_area.npy"), flood_area)
    print(f"Saved change detection mask in {output_dir}")
