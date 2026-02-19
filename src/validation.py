# src/validation.py
import os
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from sklearn.metrics import confusion_matrix, f1_score, jaccard_score
import pandas as pd

def validate(output_dir="results", ems_shp=None):
    """Compare flood raster to reference shapefile. Skip if ems_shp is None or missing."""
    if ems_shp is None or not os.path.isfile(ems_shp):
        print("Validation skipped (no reference shapefile).")
        return None
    # Prefer flood_area_new.tif if present (current run; flood_area.tif may be locked/old)
    raster_path = os.path.join(output_dir, "flood_area_new.tif")
    if not os.path.isfile(raster_path):
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
        dtype='uint8',
    )

    # Flatten arrays
    y_true = ems_raster.flatten()
    y_pred = pred_raster.flatten()

    # Metrics
    cm = confusion_matrix(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)
    iou = jaccard_score(y_true, y_pred)
    tp, fp = cm[1, 1], cm[0, 1]
    fn = cm[1, 0]
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    print("Confusion Matrix:\n", cm)
    print(f"Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1:.3f}, IoU: {iou:.3f}")

    # Save metrics
    df = pd.DataFrame({"precision": [precision], "recall": [recall], "F1_score": [f1], "IoU": [iou]})
    df.to_csv(os.path.join(output_dir, "metrics.csv"), index=False)
    return {"precision": precision, "recall": recall, "f1": f1, "iou": iou, "confusion_matrix": cm}
