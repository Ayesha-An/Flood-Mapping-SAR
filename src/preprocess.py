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

def load_dsm_for_grid(dsm_path, profile, save_aligned_path=None):
    """
    Load DSM elevation raster and reproject/resample to match the SAR image (same CRS, extent, resolution).
    Use DSM e.g. from InSAR (Sentinel-1 Elevation VV); slope/elevation will align pixel‑for‑pixel.
    Returns a 2D float array of the same shape as the SAR. Optionally save aligned DSM to save_aligned_path.
    """
    height, width = profile["height"], profile["width"]
    dst_transform = profile["transform"]
    dst_crs = profile["crs"]
    dsm_dst = np.zeros((height, width), dtype=np.float64)

    with rasterio.open(dsm_path) as src:
        src_nodata = src.nodata
        reproject(
            source=rasterio.band(src, 1),
            destination=dsm_dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            src_nodata=src_nodata,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    np.nan_to_num(dsm_dst, copy=False, nan=0.0)
    # Smooth DSM to reduce InSAR noise so slope is more stable (less over-masking of flood)
    dsm_dst = median_filter(dsm_dst.astype(np.float32), size=3)
    if save_aligned_path:
        try:
            profile_dsm = profile.copy()
            profile_dsm.update(dtype=rasterio.float32, count=1, nodata=None)
            with rasterio.open(save_aligned_path, "w", **profile_dsm) as dst:
                dst.write(dsm_dst.astype(np.float32), 1)
        except Exception:
            pass  # skip if file is locked or unwritable (e.g. open in GIS)
    return dsm_dst


def slope_from_dsm(dsm, smooth_size=3):
    """Compute slope in degrees from DSM. Smooth to reduce InSAR noise."""
    from numpy import gradient, sqrt, arctan, degrees
    x, y = gradient(dsm)
    slope = degrees(arctan(sqrt(x**2 + y**2)))
    if smooth_size > 1:
        slope = median_filter(slope.astype(np.float32), size=smooth_size)
    return slope


def slope_mask(mask, dsm, slope_thresh=15, smooth_size=3):
    """Remove water on slopes steeper than slope_thresh (degrees). Uses slope from DSM elevation.
    smooth_size: median filter on slope to reduce DSM noise (0 = no smoothing)."""
    slope = slope_from_dsm(dsm, smooth_size)
    mask[slope > slope_thresh] = 0
    return mask


def elevation_mask(mask, dsm, max_elevation_m):
    """Remove water above max_elevation_m (flood unlikely at high altitude). Uses DSM elevation."""
    mask[dsm > max_elevation_m] = 0
    return mask

def save_mask(mask, path, profile):
    """Save a binary mask as GeoTIFF"""
    profile.update(dtype=rasterio.uint8, count=1, compress="lzw")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(mask, 1)

def preprocess_images(
    pre_path, post_path, output_dir="results", dsm_path=None,
    slope_thresh=None, slope_apply_to="flood", max_elevation_m=None,
    detect_kwargs=None,
):
    """
    slope_thresh: if set (e.g. 60), apply slope mask. None = no slope.
    slope_apply_to: "flood" = save slope for detect_flood (mask flood only); "water" = mask pre/post water here.
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

    # Optional: use DSM elevation (reprojected to SAR grid so it matches the image)
    if dsm_path is not None:
        dsm_aligned_path = os.path.join(output_dir, "dsm_aligned.tif")
        dsm = load_dsm_for_grid(dsm_path, profile, save_aligned_path=dsm_aligned_path)
        if slope_thresh is not None:
            if slope_apply_to == "flood":
                # Save slope for detect_flood: mask only the flood map (keeps more flood in flat areas)
                slope_deg = slope_from_dsm(dsm, smooth_size=3)
                np.save(os.path.join(output_dir, "slope_deg.npy"), slope_deg)
            else:
                # "water": mask pre/post water by slope here (classic: remove water on steep slopes)
                pre_water = slope_mask(pre_water, dsm, slope_thresh=slope_thresh, smooth_size=3)
                post_water = slope_mask(post_water, dsm, slope_thresh=slope_thresh, smooth_size=3)
        if max_elevation_m is not None:
            pre_water = elevation_mask(pre_water, dsm, max_elevation_m)
            post_water = elevation_mask(post_water, dsm, max_elevation_m)

    # Save masks as numpy
    np.save(os.path.join(output_dir, "pre_water.npy"), pre_water)
    np.save(os.path.join(output_dir, "post_water.npy"), post_water)

    # Save masks as GeoTIFF (flood_area is produced by detect_flood.change_detection)
    save_mask(pre_water, os.path.join(output_dir, "pre_water.tif"), profile)
    save_mask(post_water, os.path.join(output_dir, "post_water.tif"), profile)

    print(f"Saved pre/post water masks in {output_dir}")
    return profile
