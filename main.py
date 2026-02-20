import streamlit as st
import time
from pyzbar.pyzbar import decode
from PIL import Image
from streamlit_back_camera_input import back_camera_input
import os 

# นำเข้า Module ที่เราแยกไว้
import utils
import packing
import ship_out
import manage_user
import upload_excel

# --- SETUP ---
st.set_page_config(page_title="Smart Picking System", page_icon="📦")
st.markdown("""
    <style>
        /* ปรับขนาด Font หัวข้อ */
        h1 { font-size: 25px !important; } 
        h2 { font-size: 20px !important; } 
        h3 { font-size: 18px !important; } 
        h4 { font-size: 15px !important; } 
        
        /* ปรับแต่งกล้อง */
        iframe[title="streamlit_back_camera_input.back_camera_input"] {
            min-height: 450px !important; 
            height: 150% !important;
        } 
        
        /* ปรับแต่งปุ่ม Disabled */
        div.stButton>button:disabled {
            background-color: #cccccc;
            color: #666666;
        }
        
        /* ปรับให้ปุ่มในหน้า Login อยู่แนวเดียวกับ Input */
        div[data-testid="column"] { align-self: flex-end; }
    </style>
""", unsafe_allow_html=True)

# --- [FIXED] STATE MANAGEMENT ---
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

init_app_state()

if st.session_state.need_reset:
    reset_keys = ['order_val', 'prod_val', 'photo_gallery', 'rider_photo_gallery', 
                  'current_order_items', 'expected_items', 'rider_scanned_orders']
    for k in reset_keys:
        st.session_state[k] = [] if 'gallery' in k or 'items' in k or 'orders' in k else ""
    st.session_state.picking_phase = 'scan'
    st.session_state.cam_counter += 1
    st.session_state.need_reset = False
    st.rerun()

# --- LOGIN FLOW ---
if not st.session_state.current_user_name:
    
    # ส่วนแสดง Logo หน้า Login (Optional)
    c_logo, c_title = st.columns([1, 4]) 
    with c_logo:
        # [แก้] ชี้ไปที่ folder picture
        if os.path.exists("picture/logo.jpg"): 
            st.image("picture/logo.jpg", width=80)
    with c_title:
        st.title("🔐 Login")
         
    df_users = utils.load_sheet_data(utils.USER_SHEET_NAME, utils.ORDER_CHECK_SHEET_ID)
    
    if 'temp_user' not in st.session_state:
        # Step 1: Scan / Input ID
        st.info("กรุณาสแกนหรือพิมพ์รหัสพนักงาน")
        c1, c2 = st.columns([3,1])
        with c1: man = st.text_input("รหัสพนักงาน (ID)", key="login_id_input")
        with c2: cam = back_camera_input("Scan", key="login_cam")
        
        uid = man if man else (decode(Image.open(cam))[0].data.decode("utf-8") if cam and decode(Image.open(cam)) else None)
        
        if uid and not df_users.empty:
            match = df_users[df_users.iloc[:,0].astype(str).str.lower().str.strip() == str(uid).lower().strip()]
            if not match.empty:
                r = match.iloc[0]
                st.session_state.temp_user = {'id': str(r[0]), 'pass': str(r[1]), 'name': r[2], 'role': r[3] if len(r)>3 else 'staff'}
                st.rerun()
            else: st.error("❌ ไม่พบรหัสพนักงานนี้")
            
    else:
        # Step 2: Confirm Name & Password
        u = st.session_state.temp_user
        
        # --- [DESIGN ใหม่] จัด layout แบบ 2 คอลัมน์ ---
        
        # แถวที่ 1: ชื่อพนักงาน + ปุ่ม Back
        c_user, c_back = st.columns([3, 1]) 
        with c_user:
            # ใช้ st.success แทน st.info เพื่อให้ดูเป็นสถานะยืนยันแล้ว
            st.success(f"👤 **{u['name']}** ({u['role']})") 
        with c_back:
            # ปุ่ม Back อยู่ท้ายชื่อ
            if st.button("⬅️ Back", use_container_width=True, help="เปลี่ยน user"):
                del st.session_state.temp_user
                st.rerun()

        # แถวที่ 2: ช่อง Password + ปุ่ม Login
        c_pass, c_login = st.columns([3, 1])
        with c_pass:
            # ใส่ label_visibility="collapsed" ถ้าอยากซ่อนคำว่า Password แต่ใส่ไว้ดีกว่าเพื่อความชัดเจน
            pw = st.text_input("Password", type="password", placeholder="กรอกรหัสผ่าน", key="login_pass")
        with c_login:
            # ใช้ CSS hack ด้านบนช่วยจัดให้ปุ่มตรงกับช่อง input
            # ปุ่ม Login อยู่ท้ายช่องรหัสผ่าน
            if st.button("🚀 Login", type="primary", use_container_width=True):
                if pw == u['pass']:
                    st.session_state.current_user_name = u['name']
                    st.session_state.current_user_id = u['id']
                    st.session_state.current_user_role = u['role']
                    del st.session_state.temp_user
                    st.toast("Welcome!", icon="🎉")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ รหัสผิด")

else:
    # --- APP NAVIGATION (SIDEBAR) ---
    with st.sidebar:
        if os.path.exists("picture/logo.jpg"):
            st.image("picture/logo.jpg", use_column_width=True)
        else:
            st.caption("No logo found in picture/ folder")
            
        st.divider()
        st.write(f"👤 **{st.session_state.current_user_name}**")
        st.caption(f"Role: {st.session_state.current_user_role}")
        
        # --- [แก้] เพิ่มเมนูอัปโหลดข้อมูลลงไป ---
        opts = ["📦 แผนกแพ็คสินค้า", "🚚 Scan ปิดตู้", "📤 อัปโหลดข้อมูล Order"]
        if st.session_state.current_user_role == 'admin': 
            opts.append("👥 จัดการพนักงาน")
        
        mode = st.radio("เลือกเมนู", opts)
        
        st.divider()
        if st.button("Logout", type="secondary", use_container_width=True): 
            st.session_state.clear()
            st.rerun()

    # --- ROUTING ---
    if mode == "📦 แผนกแพ็คสินค้า": packing.app()
    elif mode == "🚚 Scan ปิดตู้": ship_out.app()
    elif mode == "📤 อัปโหลดข้อมูล Order": upload_excel.app() # <--- เพิ่มบรรทัดนี้
    elif mode == "👥 จัดการพนักงาน": manage_user.app()
