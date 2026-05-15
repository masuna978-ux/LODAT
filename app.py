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
st.set_page_config(layout="wide", page_title="Quản lý lô đất - Bình Nghi")

st.markdown("""
    <style>
    .block-container { padding: 0rem !important; max-width: 100%; }
    
    /* Ô LỆNH (CMD) */
    div[data-testid="stTextInput"]:has(input[placeholder*="Bắt đầu"]) {
        position: fixed; bottom: 35px; left: 35px; width: 320px !important; z-index: 99999; 
    }
    div[data-testid="stTextInput"]:has(input[placeholder*="Bắt đầu"]) > div {
        background-color: rgba(15, 15, 15, 0.85) !important; 
        border: 2px solid #00FF00 !important;
        border-radius: 12px !important;
        box-shadow: 0 0 20px rgba(0, 255, 0, 0.4) !important;
    }

    /* LÀM ĐẸP SIDEBAR */
    [data-testid="stSidebar"] { background-color: #1E1E1E !important; }
    [data-testid="stSidebar"] .stForm {
        border: 1px solid #444 !important;
        padding: 20px !important;
        border-radius: 15px !important;
        background-color: #262626 !important;
    }
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

# Khởi tạo bộ nhớ tạm trong Session State nếu chưa có
if "pending_changes" not in st.session_state:
    st.session_state.pending_changes = {}

# Đọc dữ liệu từ Sheets
data = worksheet.get_all_records()
df_cloud = pd.DataFrame(data)

if df_cloud.empty or 'STT_Goc' not in df_cloud.columns:
    df_cloud = pd.DataFrame({
        'STT_Goc': gdf['STT_Goc'], 
        'TenLo': [f"Lô {i+1}" for i in range(len(gdf))], 
        'GhiChu': '', 'MauNen': '#3388ff'
    })
    worksheet.clear()
    worksheet.update([df_cloud.columns.values.tolist()] + df_cloud.values.tolist())
else:
    df_cloud['STT_Goc'] = pd.to_numeric(df_cloud['STT_Goc'])

# Merge dữ liệu gốc với dữ liệu từ Sheets
gdf_merged = gdf.merge(df_cloud[['STT_Goc', 'TenLo', 'GhiChu', 'MauNen']], on='STT_Goc', how='left')

# ÁP DỤNG CÁC THAY ĐỔI ĐANG CHỜ (PENDING) LÊN BẢN ĐỒ NGAY LẬP TỨC
for stt, changes in st.session_state.pending_changes.items():
    idx = gdf_merged[gdf_merged['STT_Goc'] == stt].index
    if not idx.empty:
        gdf_merged.loc[idx, 'TenLo'] = changes['TenLo']
        gdf_merged.loc[idx, 'GhiChu'] = changes['GhiChu']
        gdf_merged.loc[idx, 'MauNen'] = changes['MauNen']

# =========================
# 🗺️ BẢN ĐỒ
# =========================
kcn_lat, kcn_lng = 13.864639, 109.004583
m = folium.Map(location=[kcn_lat, kcn_lng], zoom_start=15, 
               tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google Satellite")

folium.Marker([kcn_lat, kcn_lng], popup="KCN Bình Nghi", icon=folium.Icon(color="red", icon="industry", prefix="fa")).add_to(m)
LocateControl(locateOptions={'enableHighAccuracy': True, 'watch': True}).add_to(m)

def style_fn(f):
    return {'fillColor': f['properties'].get('MauNen', '#3388ff'), 'color': 'white', 'weight': 1, 'fillOpacity': 0.6}

folium.GeoJson(
    gdf_merged, style_function=style_fn, 
    tooltip=folium.GeoJsonTooltip(fields=['TenLo', 'GhiChu'], aliases=['', ''], labels=False, sticky=True)
).add_to(m)

# =========================
# 🎮 Ô LỆNH CMD
# =========================
if "edit_mode" not in st.session_state: st.session_state.edit_mode = False

def cmd_callback():
    cmd = st.session_state.cmd_input.strip().lower()
    if cmd == "edit": st.session_state.edit_mode = True
    elif cmd in ["exit", "thoat"]: 
        st.session_state.edit_mode = False
        st.session_state.pending_changes = {} # Hủy các thay đổi chưa lưu khi thoát
    st.session_state.cmd_input = ""

st.text_input("Hệ thống:", key="cmd_input", on_change=cmd_callback, label_visibility="collapsed", placeholder="Bắt đầu gõ 'edit' để sửa...")

map_res = st_folium(m, width="100%", height=850, use_container_width=True, returned_objects=["last_active_drawing"])

# =========================
# 📝 SIDEBAR (THANH SỬA CHỮA)
# =========================
with st.sidebar:
    st.title("🚀 Điều hướng")
    
    # NÚT LƯU TẤT CẢ (Chỉ hiện khi có thay đổi đang chờ)
    if st.session_state.pending_changes:
        st.warning(f"Đang có {len(st.session_state.pending_changes)} thay đổi chưa lưu!")
        if st.button("💾 LƯU TẤT CẢ LÊN CLOUD", use_container_width=True, type="primary"):
            with st.spinner("Đang đồng bộ dữ liệu..."):
                for stt, changes in st.session_state.pending_changes.items():
                    idx_sheet = int(stt) + 2
                    worksheet.update(f"B{idx_sheet}:D{idx_sheet}", [[changes['TenLo'], changes['GhiChu'], changes['MauNen']]])
                st.session_state.pending_changes = {} # Xóa bộ nhớ tạm sau khi lưu
                st.success("Đã đồng bộ toàn bộ dữ liệu!")
                st.rerun()

    st.write("---")

    active = map_res.get("last_active_drawing")
    if active:
        stt_goc_sel = active["properties"].get("STT_Goc")
        
        # Lấy dữ liệu (ưu tiên lấy từ pending_changes nếu có, không thì lấy từ gdf_merged)
        if stt_goc_sel in st.session_state.pending_changes:
            data_row = st.session_state.pending_changes[stt_goc_sel]
        else:
            row = gdf_merged[gdf_merged['STT_Goc'] == stt_goc_sel].iloc[0]
            data_row = {'TenLo': row['TenLo'], 'GhiChu': row['GhiChu'], 'MauNen': row['MauNen']}

        st.subheader(f"📍 {data_row['TenLo']}")
        
        if st.session_state.edit_mode:
            # Dùng form để ghi nhận thay đổi của MỘT lô đất vào bộ nhớ tạm
            with st.form(key=f"form_{stt_goc_sel}"):
                st.write("🔧 **CHỈNH SỬA TẠM THỜI**")
                new_name = st.text_input("Tên lô đất:", value=data_row['TenLo'])
                new_note = st.text_area("Ghi chú:", value=data_row['GhiChu'])
                new_color = st.color_picker("Màu trạng thái:", value=data_row['MauNen'])
                
                if st.form_submit_button("XÁC NHẬN LÔ NÀY"):
                    st.session_state.pending_changes[stt_goc_sel] = {
                        'TenLo': new_name,
                        'GhiChu': new_note,
                        'MauNen': new_color
                    }
                    st.toast(f"Đã ghi nhớ thay đổi cho {new_name}. Hãy nhấn LƯU TẤT CẢ ở trên sau khi xong.")
                    st.rerun()
        else:
            # Chế độ xem... (giữ nguyên)
            maps_url = f"https://www.google.com/maps/dir/?api=1&destination={active['geometry']['coordinates'][0][0][1] if active['geometry']['type'] == 'Polygon' else active['geometry']['coordinates'][1]},{active['geometry']['coordinates'][0][0][0] if active['geometry']['type'] == 'Polygon' else active['geometry']['coordinates'][0]}&travelmode=driving"
            st.markdown(f'<a href="{maps_url}" target="_blank"><button style="width:100%; background:#4285F4; color:white; border:none; padding:12px; border-radius:10px; font-weight:bold; cursor:pointer;">🚗 CHỈ ĐƯỜNG ĐẾN ĐÂY</button></a>', unsafe_allow_html=True)
            if data_row['GhiChu']:
                st.write("---")
                st.write(f"📝 **Ghi chú:** {data_row['GhiChu']}")
    else:
        st.info("Hãy chọn một lô đất trên bản đồ.")
