# src/postprocess.py
import os
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape

def save_raster_and_polygons(mask, raster_path, polygon_path_geojson, polygon_path_geojson_WGS84, profile):
    """Save mask as raster and convert to vector polygons in GPKG and GeoJSON"""
    
    # Save raster
    profile.update(dtype=rasterio.uint8, count=1, compress="lzw")
    with rasterio.open(raster_path, "w", **profile) as dst:
        dst.write(mask, 1)
    print(f"Saved raster: {raster_path}")

    # Convert mask to polygons (only pixels with value 1)
    geoms = [shape(geom) for geom, val in shapes(mask, transform=profile["transform"]) if val == 1]
    gdf = gpd.GeoDataFrame(geometry=geoms, crs=profile["crs"])
    
    # Save polygons as GeoJSON
    gdf.to_file(polygon_path_geojson, driver="GeoJSON")
    print(f"Saved polygons (GeoJSON): {polygon_path_geojson}")

    # Save polygons as GeoJSON (WGS84)
    gdf = gpd.GeoDataFrame(geometry=geoms, crs=profile["crs"])
    gdf = gdf.to_crs(epsg=4326)
    gdf.to_file(polygon_path_geojson_WGS84, driver="GeoJSON")


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
