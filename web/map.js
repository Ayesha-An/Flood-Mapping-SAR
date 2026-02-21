// ------------------------------
// Create Map (do not run when opened from file:// - CORS blocks JSON)
// ------------------------------
if (window.location.protocol === 'file:') {
    // Full-page overlay is shown in index.html; skip map and fetch to avoid CORS errors
} else {
(function() {
var mapDiv = document.getElementById('map');
if (!mapDiv) {
    console.error("Map div not found!");
    alert("Map container not found. Check HTML structure.");
} else {
    console.log("Map div found, creating map...");
}

var map = L.map('map', {
    zoomControl: true,
    scrollWheelZoom: true,
    center: [48.77, 13.01], // Bavaria approximate center
    zoom: 12
});

console.log("Map created");

// ------------------------------
// Base Map
// ------------------------------
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

// ------------------------------
// Flood Layer Styles
// ------------------------------
function floodStyleNoDSM(feature) {
    return {
        color: '#4682B4', // steel blue border
        weight: 3,
        fillColor: '#ADD8E6', // light blue fill
        fillOpacity: 0.7
    };
}

function floodStyleDSM(feature) {
    return {
        color: '#008080', // teal border
        weight: 3,
        fillColor: '#20B2AA', // light sea green fill
        fillOpacity: 0.7
    };
}

function highlightFeature(e) {
    var layer = e.target;
    layer.setStyle({
        weight: 4,
        fillOpacity: 0.8
    });
    layer.bringToFront();
}

function resetHighlight(e) {
    var layer = e.target;
    if (layer.options.layerType === 'no_dsm') {
        layer.setStyle(floodStyleNoDSM());
    } else {
        layer.setStyle(floodStyleDSM());
    }
}

// ------------------------------
// Load Flood GeoJSON Layers
// ------------------------------
var floodLayerNoDSM = L.geoJSON(null, {
    style: floodStyleNoDSM,
    onEachFeature: function (feature, layer) {
        layer.options.layerType = 'no_dsm';
        layer.on({
            mouseover: highlightFeature,
            mouseout: resetHighlight,
            click: function() { layer.openPopup(); }
        });

        if (feature.properties) {
            let popupContent = "<div style='font-size:14px'><b>Flood (No DSM)</b><br>";
            for (let key in feature.properties) {
                popupContent += `<b>${key}:</b> ${feature.properties[key]}<br>`;
            }
            popupContent += "</div>";
            layer.bindPopup(popupContent);
        }
    }
});

var floodLayerDSM = L.geoJSON(null, {
    style: floodStyleDSM,
    onEachFeature: function (feature, layer) {
        layer.options.layerType = 'dsm';
        layer.on({
            mouseover: highlightFeature,
            mouseout: resetHighlight,
            click: function() { layer.openPopup(); }
        });

        if (feature.properties) {
            let popupContent = "<div style='font-size:14px'><b>Flood (DSM)</b><br>";
            for (let key in feature.properties) {
                popupContent += `<b>${key}:</b> ${feature.properties[key]}<br>`;
            }
            popupContent += "</div>";
            layer.bindPopup(popupContent);
        }
    }
});

// Load both GeoJSON files (path relative to current page so it works with serve.py or Live Server)
var dataDir = (function() {
    var path = window.location.pathname;
    if (path.endsWith('/') || path === '') return 'data/';
    return path.replace(/\/[^/]*$/, '/') + 'data/';
})();
Promise.all([
    fetch(dataDir + 'flood_area_polygons_WGS84.json').then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status + ': ' + r.statusText);
        return r.json();
    }),
    fetch(dataDir + 'flood_area_polygons_WGS84_dsm60.json').then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status + ': ' + r.statusText);
        return r.json();
    })
])
.then(([dataNoDSM, dataDSM]) => {
    console.log("Loaded No DSM:", dataNoDSM.features?.length || 0, "features");
    console.log("Loaded DSM:", dataDSM.features?.length || 0, "features");
    
    var hasLayers = false;
    
    if (dataNoDSM.features && dataNoDSM.features.length > 0) {
        floodLayerNoDSM.addData(dataNoDSM);
        floodLayerNoDSM.addTo(map);
        hasLayers = true;
        console.log("✓ Added No DSM layer:", dataNoDSM.features.length, "features");
    } else {
        console.warn("✗ No DSM data: no features found");
    }
    
    if (dataDSM.features && dataDSM.features.length > 0) {
        floodLayerDSM.addData(dataDSM);
        floodLayerDSM.addTo(map);
        hasLayers = true;
        console.log("✓ Added DSM layer:", dataDSM.features.length, "features");
    } else {
        console.warn("✗ DSM data: no features found");
    }
    
    if (!hasLayers) {
        alert("No flood polygons found in data files. Check console for details.");
        return;
    }

    var noserverMsg = document.getElementById('noserver-msg');
    if (noserverMsg) noserverMsg.style.display = 'none';

    // Add layer control after layers are created
    layerControl = L.control.layers(null, overlayMaps, {
        position: 'topright',
        collapsed: false
    }).addTo(map);
    
    // Fit bounds to show both layers
    var bounds = L.latLngBounds([]);
    var hasBounds = false;
    
    try {
        var noDSMBounds = floodLayerNoDSM.getBounds();
        if (noDSMBounds && noDSMBounds.isValid()) {
            bounds.extend(noDSMBounds);
            hasBounds = true;
            console.log("No DSM bounds:", noDSMBounds.toBBoxString());
        }
    } catch(e) {
        console.warn("Could not get No DSM bounds:", e);
    }
    
    try {
        var dsmBounds = floodLayerDSM.getBounds();
        if (dsmBounds && dsmBounds.isValid()) {
            bounds.extend(dsmBounds);
            hasBounds = true;
            console.log("DSM bounds:", dsmBounds.toBBoxString());
        }
    } catch(e) {
        console.warn("Could not get DSM bounds:", e);
    }
    
    if (hasBounds && bounds.isValid()) {
        map.fitBounds(bounds, {padding: [50, 50]});
        console.log("✓ Fitted map to bounds:", bounds.toBBoxString());
    } else {
        console.warn("✗ Could not determine bounds, staying at default view");

        map.setView([48.77, 13.01], 12);
    }
})
.catch(function(error) {
    console.error("Error loading flood layers:", error);
    var msg = document.getElementById('noserver-msg');
    if (msg) {
        msg.style.display = 'block';
        msg.innerHTML = "Flood data could not load. Use the local server: <code>cd web && python serve.py</code> then open <a href='http://localhost:8000/index.html'>http://localhost:8000/index.html</a>";
    }
    alert("Failed to load flood map data. Open the page via the server (see yellow message above).");
});

// ------------------------------
// Layer Control
// ------------------------------
var overlayMaps = {
    "Flood (No DSM)": floodLayerNoDSM,
    "Flood (DSM)": floodLayerDSM
};

// Layer control will be added after data loads
var layerControl;

// ------------------------------
// Legend
// ------------------------------
var legend = L.control({position: 'bottomright'});

legend.onAdd = function (map) {
    var div = L.DomUtil.create('div', 'info legend');
    div.innerHTML = `
        <div style="margin-bottom: 5px;">
            <i style="background: #ADD8E6; border: 2px solid #4682B4;"></i> Flood (No DSM)
        </div>
        <div>
            <i style="background: #20B2AA; border: 2px solid #008080;"></i> Flood (DSM)
        </div>
    `;
    return div;
};

legend.addTo(map);

// ------------------------------
// Scale bar
// ------------------------------
L.control.scale({position: 'bottomleft', imperial: false}).addTo(map);

})(); // end run only when not file://
}
