import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import pandas as pd
import fiona
import os

# =========================
# CONFIG & GIAO DIỆN FULL MÀN HÌNH
# =========================
st.set_page_config(
    layout="wide",
    page_title="Quản lý lô đất",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    .block-container {
        padding: 0rem !important;
        max-width: 100%;
    }
    header {visibility: hidden;} 
    
    div[data-testid="stTextInput"] {
        position: fixed;
        bottom: 30px;
        left: 30px;
        width: 350px !important;
        z-index: 99999;
        background-color: rgba(25, 25, 25, 0.9) !important; 
        border-radius: 6px !important;
        border: 1px solid #555 !important;
        box-shadow: 0px 8px 16px rgba(0,0,0,0.6) !important; 
        padding: 2px !important;
    }
    
    div[data-testid="stTextInput"] div[data-baseweb="input"] {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    
    div[data-testid="stTextInput"] input {
        background-color: transparent !important;
        color: #00FF00 !important; 
        font-family: 'Consolas', 'Courier New', monospace !important;
        font-size: 15px !important;
        caret-color: #00FF00 !important; 
        padding: 8px 15px !important;
    }
    
    div[data-testid="stTextInput"] input::placeholder {
        color: #888888 !important; 
        font-style: italic;
    }
    </style>
""", unsafe_allow_html=True)

# =========================
# SESSION & XỬ LÝ LỆNH TỰ ĐỘNG
# =========================
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False

def process_command():
    cmd = st.session_state.cmd_input.strip().lower()
    if cmd == "edit":
        st.session_state.edit_mode = True
    elif cmd in ["exit", "thoat"]:
        st.session_state.edit_mode = False
    elif cmd != "":
        st.toast(f"❌ Lỗi: Không nhận diện được lệnh '{cmd}'")
    
    st.session_state.cmd_input = ""

st.text_input(
    "Command:", 
    key="cmd_input", 
    on_change=process_command, 
    label_visibility="collapsed", 
    placeholder="Command: edit hoặc exit"
)

if st.session_state.edit_mode:
    st.info("🛠️ ĐANG SỬA: Click vào lô để chỉnh màu/ghi chú. Gõ 'exit' để thoát.")

# =========================
# ENABLE KML & LOAD DỮ LIỆU
# =========================
fiona.drvsupport.supported_drivers['KML'] = 'rw'

try:
    gdf = gpd.read_file("text7.kml", driver="KML")
except Exception as e:
    st.error(f"Lỗi đọc file KML: {e}")
    st.stop()

# =========================
# TẠO ID LÔ & GHÉP VỚI EXCEL
# =========================
gdf['TenLo'] = [f"Lô {i+1}" for i in range(len(gdf))]
excel_file = "lot_data.xlsx"

if not os.path.exists(excel_file):
    df_excel = pd.DataFrame({
        'TenLo': gdf['TenLo'],
        'GhiChu': ['' for _ in range(len(gdf))],
        'MauNen': ['#3388ff' for _ in range(len(gdf))]
    })
    df_excel.to_excel(excel_file, index=False)

df_excel = pd.read_excel(excel_file)
gdf = gdf.merge(df_excel, on='TenLo', how='left')

# =========================
# TẠO MAP
# =========================
def style_function(feature):
    return {
        'fillColor': feature['properties'].get('MauNen', '#3388ff'),
        'color': '#ffffff', # Đổi viền lô đất thành màu trắng cho nổi bật trên nền vệ tinh tối màu
        'weight': 1.5,
        'fillOpacity': 0.6
    }

centroids = gdf.to_crs(epsg=3857).geometry.centroid.to_crs(gdf.crs)
center = [centroids.y.mean(), centroids.x.mean()]

# ĐÃ SỬA: Sử dụng nền Google Satellite Hybrid
m = folium.Map(
    location=center, 
    zoom_start=16, 
    control_scale=True,
    tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", # lyrs=y: Vệ tinh + Đường giao thông
    attr="Google"
)

folium.GeoJson(
    gdf,
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(
        fields=['GhiChu'],
        aliases=[''],
        labels=False,
        sticky=True
    )
).add_to(m)

map_data = st_folium(m, width="100%", height=850, use_container_width=True)

# =========================
# LOGIC CHỈNH SỬA KHI CLICK
# =========================
if st.session_state.edit_mode:
    selected = map_data.get("last_active_drawing")
    
    if selected and "properties" in selected:
        properties = selected["properties"]
        ten_lo = properties.get("TenLo", "")
        ghi_chu = properties.get("GhiChu", "")
        mau_nen = properties.get("MauNen", "#3388ff")

        with st.sidebar:
            st.header(f"📌 Đang chọn: {ten_lo}")
            
            with st.form("edit_lot_form"):
                ghi_chu_new = st.text_area("Ghi chú lô đất:", value=ghi_chu, height=150)
                mau_nen_new = st.color_picker("Chọn màu nền:", mau_nen)
                
                submitted = st.form_submit_button("✅ Lưu dữ liệu")
                
                if submitted:
                    idx = df_excel[df_excel['TenLo'] == ten_lo].index[0]
                    df_excel.at[idx, 'GhiChu'] = ghi_chu_new
                    df_excel.at[idx, 'MauNen'] = mau_nen_new
                    df_excel.to_excel(excel_file, index=False)
                    
                    st.success("Đã lưu! Bạn có thể click tiếp lô khác trên bản đồ.")
                    st.rerun()