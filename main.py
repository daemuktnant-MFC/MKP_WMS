import streamlit as st
import time
from pyzbar.pyzbar import decode
from PIL import Image
from streamlit_back_camera_input import back_camera_input

# นำเข้า Module ที่เราแยกไว้
import utils
import packing
import ship_out
import manage_user

# --- SETUP ---
st.set_page_config(page_title="Smart Picking System", page_icon="📦")
st.markdown("""<style>iframe[title="streamlit_back_camera_input.back_camera_input"] {min-height: 450px !important; height: 150% !important;} div.stButton>button:disabled{background-color:#ccc;color:#666;}</style>""", unsafe_allow_html=True)

# --- [FIXED] STATE MANAGEMENT ---
# 1. ฟังก์ชันสำหรับกำหนดค่าเริ่มต้น (ใช้ทั้งตอนเปิดแอป และตอนกด Reset)
def init_app_state():
    defaults = {
        'picking_phase': 'scan',
        'order_val': "",
        'prod_val': "",
        'photo_gallery': [],
        'rider_photo_gallery': [],
        'current_order_items': [],
        'expected_items': [],
        'rider_scanned_orders': [],
        'cam_counter': 0,
        'current_user_name': "",
        'current_user_role': "",
        'rider_input_reset_key': 0,
        'need_reset': False
    }
    
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

# 2. เรียกใช้งานทันทีเมื่อเริ่มรันโค้ด
init_app_state()

# 3. Logic สำหรับการ Reset (เมื่อ need_reset = True)
if st.session_state.need_reset:
    # รีเซ็ตเฉพาะค่าที่เกี่ยวกับงาน (ไม่รวม User Login)
    reset_keys = ['order_val', 'prod_val', 'photo_gallery', 'rider_photo_gallery', 
                  'current_order_items', 'expected_items', 'rider_scanned_orders']
    for k in reset_keys:
        st.session_state[k] = [] if 'gallery' in k or 'items' in k or 'orders' in k else ""
    
    st.session_state.picking_phase = 'scan'
    st.session_state.cam_counter += 1
    st.session_state.need_reset = False
    st.rerun() # สั่งรันใหม่เพื่อให้ค่าอัปเดตทันที

# --- LOGIN FLOW ---
if not st.session_state.current_user_name:
    st.title("🔐 Login")
    df_users = utils.load_sheet_data(utils.USER_SHEET_NAME, utils.ORDER_CHECK_SHEET_ID)
    
    if 'temp_user' not in st.session_state:
        c1, c2 = st.columns([3,1]); man = c1.text_input("User ID"); cam = back_camera_input("Scan ID", key="login_cam")
        uid = man if man else (decode(Image.open(cam))[0].data.decode("utf-8") if cam and decode(Image.open(cam)) else None)
        
        if uid and not df_users.empty:
            match = df_users[df_users.iloc[:,0].astype(str).str.lower().str.strip() == str(uid).lower().strip()]
            if not match.empty:
                r = match.iloc[0]; st.session_state.temp_user = {'id': str(r[0]), 'pass': str(r[1]), 'name': r[2], 'role': r[3] if len(r)>3 else 'staff'}
                st.rerun()
            else: st.error("❌ User Not Found")
    else:
        u = st.session_state.temp_user
        st.info(f"👤 {u['name']} ({u['role']})"); pw = st.text_input("Password", type="password")
        if st.button("Login"):
            if pw == u['pass']:
                st.session_state.current_user_name = u['name']; st.session_state.current_user_id = u['id']; st.session_state.current_user_role = u['role']
                del st.session_state.temp_user; st.toast("Welcome!"); time.sleep(1); st.rerun()
            else: st.error("Wrong Password")
        if st.button("Back"): del st.session_state.temp_user; st.rerun()

else:
    # --- APP NAVIGATION ---
    with st.sidebar:
        st.write(f"👤 **{st.session_state.current_user_name}**")
        opts = ["📦 แผนกแพ็คสินค้า", "🚚 Scan ปิดตู้"]
        if st.session_state.current_user_role == 'admin': opts.append("👥 จัดการพนักงาน")
        mode = st.radio("Menu", opts)
        st.divider()
        if st.button("Logout"): 
            st.session_state.clear(); st.rerun()

    # --- ROUTING ---
    if mode == "📦 แผนกแพ็คสินค้า": packing.app()
    elif mode == "🚚 Scan ปิดตู้": ship_out.app()
    elif mode == "👥 จัดการพนักงาน": manage_user.app()
