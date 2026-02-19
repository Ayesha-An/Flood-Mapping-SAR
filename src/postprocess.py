# src/postprocess.py
import os
import json
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape

def save_raster_and_polygons(mask, raster_path, polygon_path_geojson, polygon_path_geojson_WGS84, profile):
    """Save mask as raster and convert to vector polygons (GeoJSON in CRS and WGS84)."""
    
    # Save raster (write to .tmp then replace; if target is locked, keep as flood_area_new.tif)
    profile.update(dtype=rasterio.uint8, count=1, compress="lzw")
    tmp_path = raster_path + ".tmp"
    with rasterio.open(tmp_path, "w", **profile) as dst:
        dst.write(mask, 1)
    try:
        os.replace(tmp_path, raster_path)
        print(f"Saved raster: {raster_path}")
    except OSError:
        new_path = os.path.join(os.path.dirname(raster_path), "flood_area_new.tif")
        os.replace(tmp_path, new_path)
        print(f"Saved raster: {new_path} (flood_area.tif was locked; close it and run again to overwrite)")

    # Convert mask to polygons (only pixels with value 1)
    geoms = [shape(geom) for geom, val in shapes(mask, transform=profile["transform"]) if val == 1]
    gdf = gpd.GeoDataFrame(geometry=geoms, crs=profile["crs"])
    gdf.to_file(polygon_path_geojson, driver="GeoJSON")
    print(f"Saved polygons (GeoJSON): {polygon_path_geojson}")
    gdf.to_crs(epsg=4326).to_file(polygon_path_geojson_WGS84, driver="GeoJSON")


def flood_area_ha_and_pixels(output_dir="results", profile=None):
    """Compute flood area (ha) and pixel count from flood_area.npy. Returns (area_ha, n_pixels)."""
    flood = np.load(os.path.join(output_dir, "flood_area.npy"))
    n = int(np.sum(flood == 1))
    if n == 0:
        return 0.0, 0
    t = profile["transform"]
    pixel_area_m2 = abs(t.a * t.e - t.b * t.d)
    return n * pixel_area_m2 / 10000.0, n


def write_summary(output_dir="results", profile=None, metrics=None, good_f1_min=0.60, good_iou_min=0.45):
    """Write summary.json with flood area (ha) and optional validation metrics. Print when results are good."""
    area_ha, n_pixels = flood_area_ha_and_pixels(output_dir, profile)
    summary = {"flood_area_ha": round(area_ha, 4), "flood_pixels": n_pixels}
    if metrics:
        summary["precision"] = round(metrics.get("precision", 0), 4)
        summary["recall"] = round(metrics.get("recall", 0), 4)
        summary["f1"] = round(metrics.get("f1", 0), 4)
        summary["iou"] = round(metrics.get("iou", 0), 4)
        f1, iou = summary["f1"], summary["iou"]
        if f1 >= good_f1_min and iou >= good_iou_min:
            summary["result_quality"] = "good"
            print(f"Result quality: GOOD (F1={f1:.3f} >= {good_f1_min}, IoU={iou:.3f} >= {good_iou_min})")
        else:
            summary["result_quality"] = "check"
            print(f"Result quality: CHECK (F1={f1:.3f}, IoU={iou:.3f}). Consider tuning or slope_thresh_deg / use_dsm.")
    path = os.path.join(output_dir, "summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary: {area_ha:.2f} ha flood | {path}")


def postprocess(output_dir="results", profile=None):
    flood_area = np.load(os.path.join(output_dir, "flood_area.npy"))
    os.makedirs(output_dir, exist_ok=True)

    save_raster_and_polygons(
        mask=flood_area,
        raster_path=os.path.join(output_dir, "flood_area.tif"),
        polygon_path_geojson=os.path.join(output_dir, "flood_area_polygons.json"),
        polygon_path_geojson_WGS84=os.path.join(output_dir, "flood_area_polygons_WGS84.json"),
        profile=profile
    )
