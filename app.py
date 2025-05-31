import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import json
from shapely.geometry import shape

# Authenticate and initialize Earth Engine
ee.Initialize(project="ee-saeiddalirisu", opt_url='https://earthengine-highvolume.googleapis.com')

st.set_page_config(layout="wide")
st.title("🌊 GEE Flood Hazard Viewer")

# Sidebar - Upload ROI GeoJSON
st.sidebar.header("Step 1: Upload ROI GeoJSON")
uploaded_file = st.sidebar.file_uploader("Upload ROI", type=["geojson"])

jet_palette = [
    '#00007F', '#0000FF', '#007FFF', '#00FFFF',
    '#7FFF7F', '#FFFF00', '#FF7F00', '#FF0000', '#7F0000'
]

if uploaded_file:
    geojson = json.load(uploaded_file)
    roi = ee.Geometry(geojson['features'][0]['geometry'])
    center = shape(geojson['features'][0]['geometry']).centroid.coords[0][::-1]

    # Get available return periods
    jrc = ee.ImageCollection("JRC/CEMS_GLOFAS/FloodHazard/v1").filterBounds(roi)
    return_periods = sorted(jrc.aggregate_array('return_period').distinct().getInfo())

    selected_rp = st.sidebar.selectbox("Step 2: Select Return Period", return_periods)
    show_map = st.sidebar.button("🛰️ Generate Flood Map")

    if show_map:
        flood_image = jrc.filter(ee.Filter.eq('return_period', selected_rp)).mosaic().clip(roi)
        stats = flood_image.reduceRegion(
            reducer=ee.Reducer.max(), geometry=roi, scale=30, maxPixels=1e9
        ).getInfo()
        vmax = stats.get('depth') or 1
        vis_params = {'min': 0.1, 'max': vmax, 'palette': jet_palette}

        # Create map
        m = folium.Map(location=center, zoom_start=10)
        map_id = ee.Image(flood_image).getMapId(vis_params)
        folium.TileLayer(
            tiles=map_id['tile_fetcher'].url_format,
            attr='Google Earth Engine',
            name=f"Flood RP {selected_rp}",
            overlay=True
        ).add_to(m)

        # Add ROI boundary
        folium.GeoJson(
            data=geojson['features'][0]['geometry'],
            name='ROI',
            style_function=lambda x: {'color': 'black', 'fillOpacity': 0}
        ).add_to(m)

        # Add legend
        legend_html = f'''
        <div style="position: fixed; bottom: 50px; left: 50px; width: 250px;
            background-color: white; border:2px solid black; z-index:9999;
            font-size:13px; padding:10px;">
            <b>Flood Legend – RP {selected_rp}</b><br>
            <table style="width: 100%;"><tr>
            {''.join([f'<td style="background-color:{c};height:12px;"></td>' for c in jet_palette])}
            </tr></table>
            <div style="display: flex; justify-content: space-between;">
                <span>0.1 m</span><span>{vmax:.2f} m</span>
            </div></div>'''
        m.get_root().html.add_child(folium.Element(legend_html))

        folium.LayerControl().add_to(m)
        st_folium(m, width=1000, height=600)

        if st.sidebar.button("📥 Export to Google Drive"):
            task = ee.batch.Export.image.toDrive(
                image=flood_image,
                description=f"FloodHazard_RP{selected_rp}",
                folder='GEE_Flood_Exports',
                fileNamePrefix=f"Flood_RP{selected_rp}",
                region=roi,
                scale=30,
                fileFormat='GeoTIFF',
                maxPixels=1e13
            )
            task.start()
            st.success("✅ Export started! Check your Google Drive.")
else:
    st.info("📤 Upload a GeoJSON file from the sidebar to begin.")
