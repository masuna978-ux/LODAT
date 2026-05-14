import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import LocateControl # Thêm thư viện định vị
import geopandas as gpd
import pandas as pd
import fiona
import os
import gspread
from google.oauth2.service_account import Credentials
import json

# =========================
# CONFIG & GIAO DIỆN FULL MÀN HÌNH
# =========================
st.set_page_config(
    layout="wide",
    page_title="Quản lý lô đất",
    initial_sidebar_state="auto" 
)

st.markdown("""
    <style>
    .block-container {
        padding: 0rem !important;
        max-width: 100%;
    }
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
    </style>
""", unsafe_allow_html=True)

# =========================
# KẾT NỐI GOOGLE SHEETS
# =========================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    return gspread.authorize(creds)

client = init_connection()
SHEET_URL = "https://docs.google.com/spreadsheets/d/1knFwpCdO9-T-L7pgSQv8Y_ikl2UMD5oHS6VzxX2HWcE/edit#gid=0"
worksheet = client.open_by_url(SHEET_URL).sheet1

# =========================
# SESSION STATE & COMMAND
# =========================
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "selected_lot" not in st.session_state:
    st.session_state.selected_lot = None

def process_command():
    cmd = st.session_state.cmd_input.strip().lower()
    if cmd == "edit":
        st.session_state.edit_mode = True
    elif cmd in ["exit", "thoat"]:
        st.session_state.edit_mode = False
        st.session_state.selected_lot = None
    st.session_state.cmd_input = ""

st.text_input("Command:", key="cmd_input", on_change=process_command, label_visibility="collapsed", placeholder="Command: edit hoặc exit")

# =========================
# LOAD DỮ LIỆU KML & GOOGLE SHEETS
# =========================
fiona.drvsupport.supported_drivers['KML'] = 'rw'
gdf = gpd.read_file("text7.kml", driver="KML")
gdf['TenLo'] = [f"Lô {i+1}" for i in range(len(gdf))]

data = worksheet.get_all_records()
if not data:
    df_cloud = pd.DataFrame({'TenLo': gdf['TenLo'], 'GhiChu': ['' for _ in range(len(gdf))], 'MauNen': ['#3388ff' for _ in range(len(gdf))]})
    worksheet.update([df_cloud.columns.values.tolist()] + df_cloud.values.tolist())
else:
    df_cloud = pd.DataFrame(data)

gdf = gdf.merge(df_cloud, on='TenLo', how='left')

# =========================
# HIỂN THỊ BẢN ĐỒ + NÚT VỊ TRÍ
# =========================
def style_function(feature):
    return {'fillColor': feature['properties'].get('MauNen', '#3388ff'), 'color': '#ffffff', 'weight': 1.5, 'fillOpacity': 0.6}

centroids = gdf.to_crs(epsg=3857).geometry.centroid.to_crs(gdf.crs)
m = folium.Map(location=[centroids.y.mean(), centroids.x.mean()], zoom_start=16, tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google")

# GẮN NÚT ĐỊNH VỊ VỊ TRÍ NGƯỜI DÙNG TẠI ĐÂY
LocateControl(
    locateOptions={'enableHighAccuracy': True},
    stopFollowing=True
).add_to(m)

folium.GeoJson(gdf, style_function=style_function, tooltip=folium.GeoJsonTooltip(fields=['GhiChu'], labels=False)).add_to(m)

if st.session_state.edit_mode:
    st.info("🛠️ CHẾ ĐỘ SỬA: Click vào lô trên bản đồ để cập nhật.")

map_data = st_folium(m, width="100%", height=850, use_container_width=True, returned_objects=["last_active_drawing"])

# =========================
# XỬ LÝ SỬA ĐỔI
# =========================
if map_data.get("last_active_drawing"):
    st.session_state.selected_lot = map_data["last_active_drawing"]

if st.session_state.edit_mode and st.session_state.selected_lot:
    props = st.session_state.selected_lot["properties"]
    ten_lo = props.get("TenLo", "")
    with st.sidebar:
        st.header(f"📌 {ten_lo}")
        with st.form("edit_form"):
            new_note = st.text_area("Ghi chú:", value=props.get("GhiChu", ""))
            new_color = st.color_picker("Màu nền:", props.get("MauNen", "#3388ff"))
            if st.form_submit_button("✅ Lưu lên mây"):
                idx = df_cloud[df_cloud['TenLo'] == ten_lo].index[0]
                worksheet.update_cell(int(idx) + 2, 2, new_note)
                worksheet.update_cell(int(idx) + 2, 3, new_color)
                st.success("Đã đồng bộ!")
                st.session_state.selected_lot = None
                st.rerun()
