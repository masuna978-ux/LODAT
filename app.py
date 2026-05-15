import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import LocateControl
import geopandas as gpd
import pandas as pd
import fiona
import gspread
from google.oauth2.service_account import Credentials
import json

# =========================
# CONFIG & GIAO DIỆN
# =========================
st.set_page_config(layout="wide", page_title="Bản đồ Lô đất - KCN Bình Nghi")

st.markdown("""
    <style>
    .block-container { padding: 0rem !important; max-width: 100%; }
    div[data-testid="stTextInput"] {
        position: fixed; bottom: 30px; left: 30px; width: 300px !important;
        z-index: 99999; background-color: rgba(0, 0, 0, 0.8) !important; 
        border-radius: 8px !important; border: 1px solid #00FF00 !important;
        padding: 5px !important;
    }
    div[data-testid="stTextInput"] input {
        color: #00FF00 !important; font-family: monospace !important;
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
# XỬ LÝ DỮ LIỆU
# =========================
fiona.drvsupport.supported_drivers['KML'] = 'rw'
gdf = gpd.read_file("text7.kml", driver="KML")
gdf['TenLo'] = [f"Lô {i+1}" for i in range(len(gdf))]

data = worksheet.get_all_records()
df_cloud = pd.DataFrame(data) if data else pd.DataFrame({'TenLo': gdf['TenLo'], 'GhiChu': '', 'MauNen': '#3388ff'})
gdf = gdf.merge(df_cloud, on='TenLo', how='left')

# =========================
# KHỞI TẠO BẢN ĐỒ
# =========================
# Tọa độ KCN Hòa Hội bạn cung cấp
kcn_lat, kcn_lng = 13.864639, 109.004583

m = folium.Map(
    location=[kcn_lat, kcn_lng], 
    zoom_start=15, 
    tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", 
    attr="Google Satellite"
)

# Thêm Marker Khu Công Nghiệp Hòa Hội
folium.Marker(
    [kcn_lat, kcn_lng],
    popup="<b>Khu Công Nghiệp Bình Nghi</b>",
    tooltip="KCN Bình Nghi",
    icon=folium.Icon(color="red", icon="industry", prefix="fa")
).add_to(m)

# Vòng tròn bán kính 1km từ KCN
folium.Circle(
    location=[kcn_lat, kcn_lng],
    radius=1000,
    color="orange",
    fill=True,
    fill_opacity=0.15,
    tooltip="Bán kính 1km tính từ KCN"
).add_to(m)

# Plugin định vị tự động cập nhật (Auto-follow)
LocateControl(
    locateOptions={'enableHighAccuracy': True, 'watch': True, 'maximumAge': 1000},
    keepCurrentZoomLevel=True,
    flyTo=True
).add_to(m)

# Lớp dữ liệu lô đất
def style_fn(f):
    return {
        'fillColor': f['properties'].get('MauNen', '#3388ff'),
        'color': 'white',
        'weight': 1,
        'fillOpacity': 0.6
    }

folium.GeoJson(
    gdf, 
    style_function=style_fn, 
    tooltip=folium.GeoJsonTooltip(fields=['TenLo', 'GhiChu'], labels=True)
).add_to(m)

# =========================
# GIAO DIỆN ĐIỀU KHIỂN
# =========================
if "edit_mode" not in st.session_state: st.session_state.edit_mode = False

def cmd_callback():
    cmd = st.session_state.cmd_input.strip().lower()
    if cmd == "edit": st.session_state.edit_mode = True
    elif cmd in ["exit", "thoat"]: st.session_state.edit_mode = False
    st.session_state.cmd_input = ""

st.text_input("Cmd:", key="cmd_input", on_change=cmd_callback, label_visibility="collapsed", placeholder="Gõ 'edit' để sửa")

# Hiển thị bản đồ
map_res = st_folium(m, width="100%", height=800, use_container_width=True, returned_objects=["last_active_drawing"])

# =========================
# SIDEBAR: CHỈ ĐƯỜNG & CHỈNH SỬA
# =========================
if map_res.get("last_active_drawing"):
    lot_props = map_res["last_active_drawing"]["properties"]
    lot_geom = map_res["last_active_drawing"]["geometry"]
    ten_lo = lot_props.get("TenLo", "N/A")
    
    # Tính tọa độ tâm để chỉ đường
    if lot_geom["type"] == "Polygon":
        c_lat, c_lng = lot_geom["coordinates"][0][0][1], lot_geom["coordinates"][0][0][0]
    else:
        c_lat, c_lng = lot_geom["coordinates"][1], lot_geom["coordinates"][0]

    with st.sidebar:
        st.title("🚀 Điều hướng nhanh")
        
        # 1. NÚT CHỈ ĐƯỜNG ĐẾN MỐC KCN (Tọa độ bạn đã gửi)
        kcn_nav_url = f"https://www.google.com/maps/dir/?api=1&destination={kcn_lat},{kcn_lng}&travelmode=driving"
        st.markdown(f'''
            <a href="{kcn_nav_url}" target="_blank">
                <button style="width:100%; background-color:#FF4B4B; color:white; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer; margin-bottom:10px;">
                    🚩 CHỈ ĐƯỜNG ĐẾN MỐC KCN
                </button>
            </a>
        ''', unsafe_allow_html=True)
        
        st.write("---") # Đường kẻ ngăn cách

        # 2. PHẦN HIỂN THỊ THÔNG TIN LÔ ĐẤT (Nếu có click chọn lô)
        if map_res.get("last_active_drawing"):
            # ... (giữ nguyên đoạn code xử lý ten_lo, c_lat, c_lng và nút chỉ đường đến lô đất đã làm ở bước trước)
        st.title(f"📍 {ten_lo}")
        
        # Nút Chỉ đường Google Maps
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={c_lat},{c_lng}&travelmode=driving"
        st.markdown(f'''
            <a href="{maps_url}" target="_blank">
                <button style="width:100%; background-color:#4285F4; color:white; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer;">
                    🚗 CHỈ ĐƯỜNG ĐẾN ĐÂY
                </button>
            </a>
        ''', unsafe_allow_html=True)
        
        st.write("---")
        
        if st.session_state.edit_mode:
            with st.form("edit_form"):
                note = st.text_area("Ghi chú lô đất:", lot_props.get("GhiChu", ""))
                color = st.color_picker("Màu trạng thái:", lot_props.get("MauNen", "#3388ff"))
                if st.form_submit_button("LƯU LÊN CLOUD"):
                    idx = df_cloud[df_cloud['TenLo'] == ten_lo].index[0]
                    worksheet.update_cell(int(idx) + 2, 2, note)
                    worksheet.update_cell(int(idx) + 2, 3, color)
                    st.success("Đã cập nhật Google Sheets!")
                    st.rerun()
        else:
            st.info(f"📝 **Ghi chú:** {lot_props.get('GhiChu', 'Chưa có thông tin')}")
            st.caption("Mẹo: Gõ 'edit' vào ô lệnh phía dưới để sửa thông tin.")
