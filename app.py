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
# 🎨 GIAO DIỆN HUD NEON
# =========================
st.set_page_config(layout="wide", page_title="Quản lý lô đất - Phù Cát")

st.markdown("""
    <style>
    .block-container { padding: 0rem !important; max-width: 100%; }
    /* Ô lệnh Cmd góc màn hình */
    div[data-testid="stTextInput"] {
        position: fixed; bottom: 35px; left: 35px; width: 320px !important; z-index: 99999; 
    }
    div[data-testid="stTextInput"] > div {
        background-color: rgba(15, 15, 15, 0.85) !important; 
        border: 2px solid #00FF00 !important;
        border-radius: 12px !important;
        box-shadow: 0 0 20px rgba(0, 255, 0, 0.4) !important;
        backdrop-filter: blur(5px);
    }
    div[data-testid="stTextInput"] input {
        color: #00FF00 !important; font-family: 'Consolas', monospace !important;
        font-size: 16px !important;
    }
    div[data-testid="stTextInput"] label { display: none !important; }
    
    /* Làm đẹp Sidebar Form */
    [data-testid="stSidebar"] .stForm {
        border: 1px solid #444 !important;
        padding: 15px !important;
        border-radius: 12px !important;
        background-color: rgba(255, 255, 255, 0.05) !important;
    }
    button { border-radius: 10px !important; transition: 0.3s !important; }
    </style>
""", unsafe_allow_html=True)

# =========================
# 🔌 KẾT NỐI DỮ LIỆU
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
# 📊 XỬ LÝ DỮ LIỆU
# =========================
fiona.drvsupport.supported_drivers['KML'] = 'rw'
gdf = gpd.read_file("text7.kml", driver="KML")
gdf['STT_Goc'] = range(len(gdf))

data = worksheet.get_all_records()
df_cloud = pd.DataFrame(data)

if df_cloud.empty or 'STT_Goc' not in df_cloud.columns:
    df_cloud = pd.DataFrame({
        'STT_Goc': gdf['STT_Goc'], 
        'TenLo': [f"Lô {i+1}" for i in range(len(gdf))], 
        'GhiChu': '', 
        'MauNen': '#3388ff'
    })
    worksheet.clear()
    worksheet.update([df_cloud.columns.values.tolist()] + df_cloud.values.tolist())
else:
    df_cloud['STT_Goc'] = pd.to_numeric(df_cloud['STT_Goc'])

gdf = gdf.merge(df_cloud[['STT_Goc', 'TenLo', 'GhiChu', 'MauNen']], on='STT_Goc', how='left')

# =========================
# 🗺️ BẢN ĐỒ
# =========================
kcn_lat, kcn_lng = 13.864639, 109.004583
m = folium.Map(location=[kcn_lat, kcn_lng], zoom_start=15, 
               tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google Satellite")

folium.Marker([kcn_lat, kcn_lng], popup="KCN Hòa Hội", icon=folium.Icon(color="red", icon="industry", prefix="fa")).add_to(m)
LocateControl(locateOptions={'enableHighAccuracy': True, 'watch': True}).add_to(m)

def style_fn(f):
    return {'fillColor': f['properties'].get('MauNen', '#3388ff'), 'color': 'white', 'weight': 1, 'fillOpacity': 0.6}

folium.GeoJson(
    gdf, 
    style_function=style_fn, 
    tooltip=folium.GeoJsonTooltip(fields=['TenLo', 'GhiChu'], aliases=['', ''], labels=False, sticky=True)
).add_to(m)

# =========================
# 🎮 ĐIỀU KHIỂN & SIDEBAR
# =========================
if "edit_mode" not in st.session_state: st.session_state.edit_mode = False

def cmd_callback():
    cmd = st.session_state.cmd_input.strip().lower()
    if cmd == "edit": st.session_state.edit_mode = True
    elif cmd in ["exit", "thoat"]: st.session_state.edit_mode = False
    st.session_state.cmd_input = ""

st.text_input("Cmd:", key="cmd_input", on_change=cmd_callback, label_visibility="collapsed", placeholder="Gõ 'edit' để sửa...")

map_res = st_folium(m, width="100%", height=850, use_container_width=True, returned_objects=["last_active_drawing"])

with st.sidebar:
    st.title("🚀 Điều hướng")
    kcn_url = f"https://www.google.com/maps/dir/?api=1&destination={kcn_lat},{kcn_lng}&travelmode=driving"
    st.markdown(f'<a href="{kcn_url}" target="_blank"><button style="width:100%; background:#FF4B4B; color:white; border:none; padding:12px; border-radius:10px; font-weight:bold; cursor:pointer;">🚩 CHỈ ĐƯỜNG ĐẾN MỐC KCN</button></a>', unsafe_allow_html=True)
    st.write("---")

    active = map_res.get("last_active_drawing")
    if active:
        stt_goc_sel = active["properties"].get("STT_Goc")
        selected_data = gdf[gdf['STT_Goc'] == stt_goc_sel].iloc[0]
        
        ten_lo_now = selected_data["TenLo"]
        ghi_chu_now = selected_data["GhiChu"]
        mau_now = selected_data["MauNen"]
        
        geom = active["geometry"]
        c_lat, c_lng = (geom["coordinates"][0][0][1], geom["coordinates"][0][0][0]) if geom["type"] == "Polygon" else (geom["coordinates"][1], geom["coordinates"][0])

        # Tiêu đề 📍 sẽ cập nhật theo tên mới nhất
        st.subheader(f"📍 {ten_lo_now}")
        
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={c_lat},{c_lng}&travelmode=driving"
        st.markdown(f'<a href="{maps_url}" target="_blank"><button style="width:100%; background:#4285F4; color:white; border:none; padding:12px; border-radius:10px; font-weight:bold; cursor:pointer;">🚗 CHỈ ĐƯỜNG ĐẾN ĐÂY</button></a>', unsafe_allow_html=True)
        st.write("---")
        
        if st.session_state.edit_mode:
            # TẤT CẢ Ô NHẬP ĐỀU NẰM TRONG FORM NÀY
            with st.form("edit_form"):
                st.markdown("**Sửa thông tin:**")
                # Gộp "Tên lô đất" vào đây
                new_name = st.text_input("Tên lô mới:", value=ten_lo_now)
                new_note = st.text_area("Ghi chú mới:", value=ghi_chu_now)
                new_color = st.color_picker("Màu trạng thái:", mau_now)
                
                col1, col2 = st.columns(2)
                if col1.form_submit_button("🚀 LƯU"):
                    idx_sheet = int(stt_goc_sel) + 2
                    worksheet.update(f"B{idx_sheet}:D{idx_sheet}", [[new_name, new_note, new_color]])
                    st.toast(f"Đã lưu {new_name}!")
                    st.rerun()
                
                if col2.form_submit_button("⏩ BỎ QUA"):
                    st.rerun()
        else:
            if ghi_chu_now: st.write(ghi_chu_now)
    else:
        st.info("Hãy chọn một lô đất trên bản đồ.")
