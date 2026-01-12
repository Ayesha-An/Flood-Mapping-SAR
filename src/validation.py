# src/validation.py
import os
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from sklearn.metrics import confusion_matrix, f1_score, jaccard_score
import pandas as pd

def validate(output_dir="results", ems_shp=None):
    raster_path = os.path.join(output_dir, "flood_area.tif")
    with rasterio.open(raster_path) as src:
        profile = src.profile
        pred_raster = src.read(1)
        raster_crs = src.crs

    # Read EMS shapefile
    ems_gdf = gpd.read_file(ems_shp).to_crs(raster_crs)

    # Rasterize EMS
    ems_raster = rasterize(
        [(geom, 1) for geom in ems_gdf.geometry],
        out_shape=pred_raster.shape,
        transform=profile['transform'],
        fill=0,
        dtype='uint8'
    )

    # Flatten arrays
    y_true = ems_raster.flatten()
    y_pred = pred_raster.flatten()

    # Metrics
    cm = confusion_matrix(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)
    iou = jaccard_score(y_true, y_pred)

    print("Confusion Matrix:\n", cm)
    print(f"F1-score: {f1:.3f}, IoU: {iou:.3f}")

    # Save metrics
    df = pd.DataFrame({"F1_score": [f1], "IoU": [iou]})
    df.to_csv(os.path.join(output_dir, "metrics.csv"), index=False)
