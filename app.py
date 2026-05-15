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
st.set_page_config(layout="wide", page_title="Quản lý lô đất - KCN Hòa Hội")

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

# Tạo STT gốc để cố định dòng trên Sheets ngay cả khi đổi tên lô
gdf['STT_Goc'] = range(len(gdf))

data = worksheet.get_all_records()
if not data:
    # Nếu Sheets trống, tạo dữ liệu mặc định
    df_cloud = pd.DataFrame({
        'STT_Goc': gdf['STT_Goc'], 
        'TenLo': [f"Lô {i+1}" for i in range(len(gdf))], 
        'GhiChu': '', 
        'MauNen': '#3388ff'
    })
    worksheet.update([df_cloud.columns.values.tolist()] + df_cloud.values.tolist())
else:
    df_cloud = pd.DataFrame(data)

# Merge dữ liệu từ Sheets vào bản đồ qua cột STT_Goc
gdf = gdf.merge(df_cloud[['STT_Goc', 'TenLo', 'GhiChu', 'MauNen']], on='STT_Goc', how='left')

# =========================
# KHỞI TẠO BẢN ĐỒ
# =========================
kcn_lat, kcn_lng = 13.864639, 109.004583
m = folium.Map(location=[kcn_lat, kcn_lng], zoom_start=15, 
               tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google Satellite")

# Marker KCN
folium.Marker([kcn_lat, kcn_lng], popup="KCN Hòa Hội", icon=folium.Icon(color="red", icon="industry", prefix="fa")).add_to(m)

# Auto-follow GPS
LocateControl(locateOptions={'enableHighAccuracy': True, 'watch': True}).add_to(m)

# Lớp dữ liệu lô đất với Tooltip sạch (Không hiện TenLo: GhiChu:)
def style_fn(f):
    return {'fillColor': f['properties'].get('MauNen', '#3388ff'), 'color': 'white', 'weight': 1, 'fillOpacity': 0.6}

folium.GeoJson(
    gdf, 
    style_function=style_fn, 
    tooltip=folium.GeoJsonTooltip(
        fields=['TenLo', 'GhiChu'], 
        aliases=['', ''], # Bỏ nhãn tiêu đề
        labels=False,      # Tắt hiển thị nhãn
        sticky=True
    )
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

map_res = st_folium(m, width="100%", height=800, use_container_width=True, returned_objects=["last_active_drawing"])

# =========================
# SIDEBAR: ĐIỀU HƯỚNG & QUẢN LÝ
# =========================
with st.sidebar:
    st.title("🚀 Điều hướng nhanh")
    kcn_url = f"https://www.google.com/maps/dir/?api=1&destination={kcn_lat},{kcn_lng}&travelmode=driving"
    st.markdown(f'<a href="{kcn_url}" target="_blank"><button style="width:100%; background:#FF4B4B; color:white; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer;">🚩 CHỈ ĐƯỜNG ĐẾN MỐC KCN</button></a>', unsafe_allow_html=True)
    st.write("---")

    active_drawing = map_res.get("last_active_drawing")
    if active_drawing:
        props = active_drawing["properties"]
        geom = active_drawing["geometry"]
        stt_goc = props.get("STT_Goc")
        ghi_chu_hien_tai = props.get("GhiChu", "")
        
        # Tọa độ tâm lô để chỉ đường
        if geom["type"] == "Polygon":
            c_lat, c_lng = geom["coordinates"][0][0][1], geom["coordinates"][0][0][0]
        else:
            c_lat, c_lng = geom["coordinates"][1], geom["coordinates"][0]

        st.subheader(f"📍 {props.get('TenLo')}")
        
        # Nút dẫn đường đến lô đất
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={c_lat},{c_lng}&travelmode=driving"
        st.markdown(f'<a href="{maps_url}" target="_blank"><button style="width:100%; background:#4285F4; color:white; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer;">🚗 CHỈ ĐƯỜNG ĐẾN ĐÂY</button></a>', unsafe_allow_html=True)
        st.write("---")
        
        if st.session_state.edit_mode:
            with st.form("edit_form"):
                # Cho phép sửa cả tên lô đất
                new_name = st.text_input("Tên lô đất:", value=props.get("TenLo"))
                new_note = st.text_area("Nội dung ghi chú:", value=ghi_chu_hien_tai)
                new_color = st.color_picker("Màu trạng thái:", props.get("MauNen", "#3388ff"))
                if st.form_submit_button("LƯU THÔNG TIN"):
                    # Tìm đúng dòng trên Sheets dựa vào STT_Goc
                    idx_sheet = int(stt_goc) + 2
                    worksheet.update_cell(idx_sheet, 2, new_name)  # Cột B: TenLo
                    worksheet.update_cell(idx_sheet, 3, new_note)  # Cột C: GhiChu
                    worksheet.update_cell(idx_sheet, 4, new_color) # Cột D: MauNen
                    st.success("Đã cập nhật!")
                    st.rerun()
        else:
            # Chế độ xem: Chỉ hiện những gì đã ghi
            if ghi_chu_hien_tai:
                st.write(ghi_chu_hien_tai)
    else:
        st.write("👉 *Hãy chọn một lô đất trên bản đồ.*")
