# Flood Area Mapping – Bavaria 2024

This project maps **flooded areas in Bavaria** using **Sentinel-1 SAR data** from two dates (May and June 2024) and performs **change detection** to identify flood extents.


## Web Map Preview

![Flooded Area Map](results/Flooded_area.png)(http://127.0.0.1:5500/web/index.html)


## Data Sources

- **Sentinel-1 SAR**: Used for flood detection (May & June 2024).  
- **EMSN 199 dataset**: Downloaded from Copernicus Emergency Management Service for validation.  
  [EMSN 199](https://riskandrecovery.emergency.copernicus.eu/EMSN199/?utm_source=chatgpt.com)


## Methodology

1. Preprocess Sentinel-1 data for both dates using SNAP software.  
2. Perform **change detection** to identify flood-affected areas.  
3. Compare results with **EMSN 199 reference dataset** for validation.  
4. Generate **interactive web map** using Leaflet for visualization.  


## Results

**Confusion Matrix:**
[[2925305 11250]
[ 27325 35895]]
- **F1-score:** 0.650  
- **Intersection over Union (IoU):** 0.482  

These results indicate good agreement with EMSN 199, though accuracy can be further improved by combining **other datasets** such as DEM and spectral data.


## Future Work

- Incorporate **DEM** and **spectral datasets** to improve detection accuracy.  
- Extend analysis to **larger temporal coverage** for seasonal flood monitoring.  
- Optimize web map for **faster loading and interactive analytics**.


## License

This project is open-source. Data usage complies with Sentinel-1 and Copernicus EMSN 199 policies.
