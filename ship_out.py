import streamlit as st
import pandas as pd
from PIL import Image
from pyzbar.pyzbar import decode 
import io 
import time
from streamlit_back_camera_input import back_camera_input
import utils 
import gspread # ต้อง import gspread ด้วยเพื่อให้ helper ทำงานได้

# Helper: Load History
def load_rider_history():
    try:
        creds = utils.get_credentials(); gc = gspread.authorize(creds); sh = gc.open_by_key(utils.LOG_SHEET_ID)
        worksheet = sh.worksheet(utils.RIDER_SHEET_NAME); records = worksheet.get_all_records()
        df = pd.DataFrame(records); return df['Order ID'].astype(str).str.upper().tolist()
    except: return []

# Helper: Save Rider Log
def save_rider_log(picker_name, order_id, file_ids_list, folder_name, license_plate):
    try:
        creds = utils.get_credentials(); gc = gspread.authorize(creds); sh = gc.open_by_key(utils.LOG_SHEET_ID)
        try: worksheet = sh.worksheet(utils.RIDER_SHEET_NAME)
        except: worksheet = sh.add_worksheet(title=utils.RIDER_SHEET_NAME, rows="1000", cols="10")
        ts = utils.get_thai_time()
        links = "\n".join([f"https://drive.google.com/open?id={fid}" for fid in file_ids_list])
        worksheet.append_row([ts, picker_name, order_id, license_plate, folder_name, links])
    except Exception as e: st.warning(f"⚠️ Log Error: {e}")

def app():
    st.title("🚚 Scan ปิดตู้")
    df_order_data = utils.load_sheet_data(utils.ORDER_DATA_SHEET_NAME, utils.ORDER_CHECK_SHEET_ID)
    rider_lp = st.text_input("🚛 ทะเบียนรถ", key="rider_lp_input").strip()

    st.markdown("#### 1. Scan Tracking")
    col1, col2 = st.columns([3, 1])
    man_ord = col1.text_input("Tracking ID", key=f"r_ord_{st.session_state.rider_input_reset_key}").strip().upper()
    with col2: st.write(""); st.write(""); sub = st.button("OK", use_container_width=True)
    
    scan = back_camera_input("Scan Tracking", key=f"r_cam_{st.session_state.cam_counter}")
    curr = man_ord if sub and man_ord else ""
    if scan and not curr:
        res = decode(Image.open(scan))
        if res: curr = res[0].data.decode("utf-8").upper()

    if curr:
        valid_list = df_order_data['Tracking'].astype(str).str.upper().tolist() if not df_order_data.empty else []
        exists_local = any(o['id'] == curr for o in st.session_state.rider_scanned_orders)
        
        if curr not in valid_list: 
            utils.play_sound('error')
            st.error("⛔ ไม่พบ Tracking")
            time.sleep(1.5)
            st.session_state.rider_input_reset_key += 1
            st.rerun()
            
        elif exists_local: 
            utils.play_sound('error')
            st.error("⚠️ สแกนซ้ำ! (สแกนไปแล้ว)")
            time.sleep(1.5)
            st.session_state.rider_input_reset_key += 1
            st.rerun()
            
        else:
            st.session_state.rider_scanned_orders.append({'id': curr})
            
            # --- [แก้ไข] เปลี่ยนเป็นเสียง success และเพิ่มหน่วงเวลา ---
            utils.play_sound('success') 
            st.success(f"✅ เพิ่ม {curr} สำเร็จ!")
            time.sleep(1) # หน่วงเวลา 1 วินาทีให้เบราว์เซอร์เล่นเสียงให้จบก่อน
            
            st.session_state.rider_input_reset_key += 1
            st.session_state.cam_counter += 1
            st.rerun()
        # --------------------------------------------------

    # --- ส่วนแสดงรายการและถ่ายรูป (ทำงานเมื่อมี Order ในตะกร้า) ---
    if st.session_state.rider_scanned_orders:
        st.write(f"📋 สแกนแล้ว ({len(st.session_state.rider_scanned_orders)})")
        for i, o in enumerate(st.session_state.rider_scanned_orders):
            c1, c2 = st.columns([4, 1])
            c1.write(f"{i+1}. **{o['id']}**")
            if c2.button("ลบ", key=f"rdel_{i}"): st.session_state.rider_scanned_orders.pop(i); st.rerun()
        
        st.markdown("#### 2. ถ่ายรูปปิดตู้")
        
        # แสดงรูปที่ถ่ายไปแล้ว
        if st.session_state.rider_photo_gallery:
            cols = st.columns(3)
            for i, img in enumerate(st.session_state.rider_photo_gallery):
                with cols[i]: st.image(img, use_column_width=True)
        
        # กล้องถ่ายรูป (แสดงเมื่อรูปยังไม่ครบ 3)
        if len(st.session_state.rider_photo_gallery) < 3:
            r_img = back_camera_input("ถ่ายรูป", key=f"r_cam_act_{st.session_state.cam_counter}")
            if r_img:
                img = Image.open(r_img)
                
                # --- แปลงโหมดสี (แก้ Error JPEG) ---
                if img.mode in ("RGBA", "P"): 
                    img = img.convert("RGB")
                # -------------------------------

                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=90)
                st.session_state.rider_photo_gallery.append(buf.getvalue())
                st.session_state.cam_counter += 1
                st.rerun()
        
        # ปุ่มยืนยัน (แสดงเมื่อมีรูปอย่างน้อย 1 รูป)
        if len(st.session_state.rider_photo_gallery) > 0:
            if st.button("🚀 ยืนยันบันทึก", type="primary", use_container_width=True):
                with st.spinner("🚀 Saving..."):
                    srv = utils.authenticate_drive()
                    fid, fname = utils.get_rider_daily_folder(srv, utils.MAIN_FOLDER_ID)
                    ts = utils.get_thai_ts_filename(); lp = rider_lp if rider_lp else "NoPlate"
                    up_ids = []
                    
                    # Upload รูป
                    for i, img in enumerate(st.session_state.rider_photo_gallery):
                        fn = f"{lp}_{ts}_{i+1}.jpg"
                        up_ids.append(utils.upload_photo(srv, img, fn, fid))
                    
                    # Save Logs
                    for o in st.session_state.rider_scanned_orders:
                        save_rider_log(st.session_state.current_user_name, o['id'], up_ids, fname, lp)
                    
                    utils.play_sound('success'); st.success("บันทึกสำเร็จ!"); time.sleep(2); st.session_state.need_reset = True; st.rerun()
