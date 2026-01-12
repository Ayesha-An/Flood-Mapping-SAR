# src/run_pipeline.py
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

PRE_FILE = os.path.join(DATA_DIR, "may.tif")
POST_FILE = os.path.join(DATA_DIR, "june.tif")
EMS_FILE = os.path.join(DATA_DIR, "EMSN_199.shp")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import preprocess
import detect_flood
import postprocess
import validation

# 1️⃣ Preprocess → detect water and save pre/post/flood masks as GeoTIFF
profile = preprocess.preprocess_images(PRE_FILE, POST_FILE, output_dir=RESULTS_DIR)

# 2️⃣ Optional: redundant, but keeps structure
detect_flood.change_detection(output_dir=RESULTS_DIR)

# 3️⃣ Postprocess → generate flood polygons
postprocess.postprocess(output_dir=RESULTS_DIR, profile=profile)

# 4️⃣ Validate against EMS mask
validation.validate(output_dir=RESULTS_DIR, ems_shp=EMS_FILE)

print("Pipeline finished! Check the results folder.")
