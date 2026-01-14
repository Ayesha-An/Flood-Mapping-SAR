// ------------------------------
// Create Map
// ------------------------------
var map = L.map('map', {
    zoomControl: true,
    scrollWheelZoom: true
});

// ------------------------------
// Base Map
// ------------------------------
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

// ------------------------------
// Flood Layer Style & Hover
// ------------------------------
function floodStyle(feature) {
    return {
        color: '#0000ff', // blue border
        weight: 2,
        fillColor: '#3399ff', // light blue fill
        fillOpacity: 0.6
    };
}

function highlightFeature(e) {
    var layer = e.target;
    layer.setStyle({
        weight: 3,
        color: '#0000cc',
        fillOpacity: 0.8
    });
    layer.bringToFront();
}

function resetHighlight(e) {
    floodLayer.resetStyle(e.target);
}

// ------------------------------
// Load Flood GeoJSON
// ------------------------------
var floodLayer;

fetch('data/flood_area_polygons_WGS84.json')
    .then(response => response.json())
    .then(data => {
        floodLayer = L.geoJSON(data, {
            style: floodStyle,
            onEachFeature: function (feature, layer) {
                layer.on({
                    mouseover: highlightFeature,
                    mouseout: resetHighlight,
                    click: function() { layer.openPopup(); }
                });

                if (feature.properties) {
                    let popupContent = "<div style='font-size:14px'>";
                    for (let key in feature.properties) {
                        popupContent += `<b>${key}:</b> ${feature.properties[key]}<br>`;
                    }
                    popupContent += "</div>";
                    layer.bindPopup(popupContent);
                }
            }
        }).addTo(map);

        map.fitBounds(floodLayer.getBounds());
    })
    .catch(error => {
        console.error("Error loading flood layer:", error);
        alert("Failed to load flood map.");
    });

// ------------------------------
// Legend
// ------------------------------
var legend = L.control({position: 'bottomright'});

legend.onAdd = function (map) {
    var div = L.DomUtil.create('div', 'info legend');
    div.innerHTML = "<i></i> Flooded Area";
    return div;
};

legend.addTo(map);

// ------------------------------
// Scale bar
// ------------------------------
L.control.scale({position: 'bottomleft', imperial: false}).addTo(map);
