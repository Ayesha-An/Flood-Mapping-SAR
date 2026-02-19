# src/detect_flood.py
import os
import numpy as np

def _load_exclude_mask(path, profile):
    """Load binary mask (raster or shapefile) on same grid as profile. 1 = exclude from flood (e.g. river)."""
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.features import rasterize
    import geopandas as gpd
    path = path.replace("/", os.sep).replace("\\", os.sep)
    h, w = profile["height"], profile["width"]
    transform = profile["transform"]
    crs = profile["crs"]
    out = np.zeros((h, w), dtype=np.uint8)
    if path.lower().endswith(".tif") or path.lower().endswith(".tiff"):
        with rasterio.open(path) as src:
            reproject(
                source=rasterio.band(src, 1),
                destination=out,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=crs,
                resampling=Resampling.nearest,
            )
    else:
        gdf = gpd.read_file(path).to_crs(crs)
        out = rasterize(
            [(g, 1) for g in gdf.geometry],
            out_shape=(h, w),
            transform=transform,
            fill=0,
            dtype="uint8",
        )
    return (out != 0)

def change_detection(output_dir="results", refine=False, exclude_water_path=None, profile=None):
    """Change detection: flood = post_water and not pre_water. Optionally exclude river/permanent water."""
    pre_water = np.load(os.path.join(output_dir, "pre_water.npy"))
    post_water = np.load(os.path.join(output_dir, "post_water.npy"))

    flood_area = np.logical_and(post_water == 1, pre_water == 0).astype(np.uint8)
    if exclude_water_path and os.path.isfile(exclude_water_path) and profile is not None:
        exclude = _load_exclude_mask(exclude_water_path, profile)
        flood_area[exclude] = 0
    if refine:
        from skimage.morphology import closing, disk
        flood_area = closing(flood_area, disk(1)).astype(np.uint8)
    np.save(os.path.join(output_dir, "flood_area.npy"), flood_area)
    print(f"Saved change detection mask in {output_dir}")
