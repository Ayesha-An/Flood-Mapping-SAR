# src/preprocess.py
import os
import numpy as np
import rasterio
from skimage.morphology import opening, closing, disk, remove_small_objects
from scipy.ndimage import median_filter

def load_sar(path):
    """Load Sentinel-1 GRD image: VH=band1, VV=band2"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with rasterio.open(path) as src:
        vh = src.read(1).astype(float)
        vv = src.read(2).astype(float)
        profile = src.profile
    return vv, vh, profile

def detect_water(vv, vh, percentile=90, vv_thresh=0.03, vh_thresh=0.01, small_object_size=2000):
    """
    Conservative water detection:
    1. VV/VH dual threshold
    2. Log-ratio threshold
    3. Morphological cleaning
    4. Small object removal (to remove isolated speckles)
    """
    # 1. Dual threshold
    mask_dual = np.logical_and(vv < vv_thresh, vh < vh_thresh)

    # 2. Log-ratio threshold
    log_ratio = np.log(vv + 1e-6) - np.log(vh + 1e-6)
    mask_ratio = log_ratio > np.percentile(log_ratio, percentile)

    # 3. Combine masks
    mask = np.logical_or(mask_dual, mask_ratio).astype(np.uint8)

    # 4. Morphological cleaning
    mask = opening(mask, disk(2))
    mask = closing(mask, disk(2))
    mask = median_filter(mask, size=3)

    # 5. Remove very small objects (conservative)
    mask = remove_small_objects(mask.astype(bool), min_size=small_object_size).astype(np.uint8)

    return mask

def slope_mask(mask, dem, slope_thresh=5):
    """
    Optional: remove water on steep slopes using DEM
    """
    from numpy import gradient, sqrt, arctan, degrees
    x, y = gradient(dem)
    slope = degrees(arctan(sqrt(x**2 + y**2)))
    mask[slope > slope_thresh] = 0
    return mask

def save_mask(mask, path, profile):
    """Save a binary mask as GeoTIFF"""
    profile.update(dtype=rasterio.uint8, count=1, compress="lzw")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(mask, 1)

def preprocess_images(pre_path, post_path, output_dir="results", dem_path=None):
    os.makedirs(output_dir, exist_ok=True)

    # Load Sentinel-1 images
    pre_vv, pre_vh, profile = load_sar(pre_path)
    post_vv, post_vh, _ = load_sar(post_path)

    # Detect water
    pre_water = detect_water(pre_vv, pre_vh)
    post_water = detect_water(post_vv, post_vh)

    # Optional: apply slope masking if DEM is provided
    if dem_path is not None:
        with rasterio.open(dem_path) as src:
            dem = src.read(1)
        pre_water = slope_mask(pre_water, dem)
        post_water = slope_mask(post_water, dem)

    # Save masks as numpy
    np.save(os.path.join(output_dir, "pre_water.npy"), pre_water)
    np.save(os.path.join(output_dir, "post_water.npy"), post_water)

    # Save masks as GeoTIFF
    save_mask(pre_water, os.path.join(output_dir, "pre_water.tif"), profile)
    save_mask(post_water, os.path.join(output_dir, "post_water.tif"), profile)

    # Change detection: new flood areas
    flood_area = np.logical_and(post_water == 1, pre_water == 0).astype(np.uint8)
    np.save(os.path.join(output_dir, "flood_area.npy"), flood_area)
    save_mask(flood_area, os.path.join(output_dir, "flood_area.tif"), profile)

    print(f"Saved pre/post water masks and flood mask in {output_dir}")
    return profile
