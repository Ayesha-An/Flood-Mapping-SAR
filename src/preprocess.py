# src/preprocess.py
import os
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
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

def detect_water(
    vv, vh,
    percentile=88,
    vv_thresh=0.035,
    vh_thresh=0.012,
    small_object_size=2000,
    morph_radius=2,
):
    """
    Water detection: VV/VH thresholds + log-ratio + morphology + small-object removal.
    Defaults tuned for best F1 vs EMS reference (run src/optimize_detection_parameters.py to search).
    """
    # 1. Dual threshold
    mask_dual = np.logical_and(vv < vv_thresh, vh < vh_thresh)

    # 2. Log-ratio threshold
    log_ratio = np.log(vv + 1e-6) - np.log(vh + 1e-6)
    mask_ratio = log_ratio > np.percentile(log_ratio, percentile)

    # 3. Combine masks
    mask = np.logical_or(mask_dual, mask_ratio).astype(np.uint8)

    # 4. Morphological cleaning (light: preserve flood boundaries)
    selem = disk(morph_radius)
    mask = opening(mask, selem)
    mask = closing(mask, selem)
    mask = median_filter(mask, size=3)

    # 5. Remove only very small speckles, keep small flood patches
    mask = remove_small_objects(mask.astype(bool), min_size=small_object_size).astype(np.uint8)

    return mask

def load_dem_for_grid(dem_path, profile, save_aligned_path=None):
    """
    Load DEM and reproject/resample to match the SAR image (same CRS, extent, resolution).
    This makes the DEM compatible with the image so slope/elevation align pixel‑for‑pixel.
    Returns a 2D float array of the same shape as the SAR. Optionally save aligned DEM to save_aligned_path.
    """
    height, width = profile["height"], profile["width"]
    dst_transform = profile["transform"]
    dst_crs = profile["crs"]
    dem_dst = np.zeros((height, width), dtype=np.float64)

    with rasterio.open(dem_path) as src:
        src_nodata = src.nodata
        reproject(
            source=rasterio.band(src, 1),
            destination=dem_dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            src_nodata=src_nodata,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    np.nan_to_num(dem_dst, copy=False, nan=0.0)
    if save_aligned_path:
        try:
            profile_dem = profile.copy()
            profile_dem.update(dtype=rasterio.float32, count=1, nodata=None)
            with rasterio.open(save_aligned_path, "w", **profile_dem) as dst:
                dst.write(dem_dst.astype(np.float32), 1)
        except Exception:
            pass  # skip if file is locked or unwritable (e.g. open in GIS)
    return dem_dst


def slope_mask(mask, dem, slope_thresh=15):
    """Remove water on slopes steeper than slope_thresh (degrees)."""
    from numpy import gradient, sqrt, arctan, degrees
    x, y = gradient(dem)
    slope = degrees(arctan(sqrt(x**2 + y**2)))
    mask[slope > slope_thresh] = 0
    return mask


def elevation_mask(mask, dem, max_elevation_m):
    """Remove water above max_elevation_m (flood unlikely at high altitude)."""
    mask[dem > max_elevation_m] = 0
    return mask

def save_mask(mask, path, profile):
    """Save a binary mask as GeoTIFF"""
    profile.update(dtype=rasterio.uint8, count=1, compress="lzw")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(mask, 1)

def preprocess_images(
    pre_path, post_path, output_dir="results", dem_path=None,
    slope_thresh=None, max_elevation_m=None,
    detect_kwargs=None,
):
    """
    slope_thresh: if set (e.g. 35), remove water on steeper slopes. None = no slope masking.
    detect_kwargs: optional overrides for water detection (percentile, vv_thresh, vh_thresh, etc.).
    """
    os.makedirs(output_dir, exist_ok=True)
    detect_kwargs = detect_kwargs or {}

    # Load Sentinel-1 images
    pre_vv, pre_vh, profile = load_sar(pre_path)
    post_vv, post_vh, _ = load_sar(post_path)

    # Detect water (same params for pre and post)
    pre_water = detect_water(pre_vv, pre_vh, **detect_kwargs)
    post_water = detect_water(post_vv, post_vh, **detect_kwargs)

    # Optional: use DEM (reprojected to SAR grid so it matches the image)
    if dem_path is not None:
        dem_aligned_path = os.path.join(output_dir, "dem_aligned.tif")
        dem = load_dem_for_grid(dem_path, profile, save_aligned_path=dem_aligned_path)
        if slope_thresh is not None:
            pre_water = slope_mask(pre_water, dem, slope_thresh=slope_thresh)
            post_water = slope_mask(post_water, dem, slope_thresh=slope_thresh)
        if max_elevation_m is not None:
            pre_water = elevation_mask(pre_water, dem, max_elevation_m)
            post_water = elevation_mask(post_water, dem, max_elevation_m)

    # Save masks as numpy
    np.save(os.path.join(output_dir, "pre_water.npy"), pre_water)
    np.save(os.path.join(output_dir, "post_water.npy"), post_water)

    # Save masks as GeoTIFF (flood_area is produced by detect_flood.change_detection)
    save_mask(pre_water, os.path.join(output_dir, "pre_water.tif"), profile)
    save_mask(post_water, os.path.join(output_dir, "post_water.tif"), profile)

    print(f"Saved pre/post water masks in {output_dir}")
    return profile
