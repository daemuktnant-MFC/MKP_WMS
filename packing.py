import streamlit as st
import pandas as pd
from PIL import Image
from pyzbar.pyzbar import decode 
import io 
import time
from streamlit_back_camera_input import back_camera_input
import utils 

# --- CALLBACK FUNCTION ---
def go_to_pack_phase():
    st.session_state.picking_phase = 'pack'

def app():
    st.title("📦 ระบบแพ็คสินค้า")
    df_order_data = utils.load_sheet_data(utils.ORDER_DATA_SHEET_NAME, utils.ORDER_CHECK_SHEET_ID)

    # --- Phase 1: SCAN ---
    if st.session_state.picking_phase == 'scan':
        st.markdown("#### 1. Scan Tracking")
        if not st.session_state.order_val:
            col1, col2 = st.columns([3, 1])
            manual_order = col1.text_input("พิมพ์ Tracking ID", key="pack_order_man").strip().upper()
            if manual_order: st.session_state.order_val = manual_order; st.rerun()
            scan_order = back_camera_input("แตะเพื่อสแกน Tracking", key=f"pack_cam_{st.session_state.cam_counter}")
            if scan_order:
                res = decode(Image.open(scan_order))
                if res: st.session_state.order_val = res[0].data.decode("utf-8").upper(); st.rerun()
        else:
            c1, c2 = st.columns([3, 1])
            with c1: st.success(f"📦 Tracking: **{st.session_state.order_val}**")
            with c2: 
                if st.button("เปลี่ยน"): st.session_state.need_reset = True; st.rerun()

        if st.session_state.order_val:
            if df_order_data.empty: st.error("❌ ไม่พบข้อมูล Order Data")
            else:
                if not st.session_state.expected_items:
                    matches = df_order_data[df_order_data['Tracking'] == st.session_state.order_val]
                    matches = matches.drop_duplicates(subset=['Barcode'], keep='first')
                    if matches.empty: utils.play_sound('error'); st.error(f"⛔ ไม่พบ Tracking ในระบบ!"); time.sleep(2); st.session_state.order_val = ""; st.rerun()
                    else: st.session_state.expected_items = matches.to_dict('records')

            if st.session_state.expected_items:
                st.info(f"📋 สินค้าต้องแพ็ค ({len(st.session_state.expected_items)}):")
                st.dataframe(pd.DataFrame(st.session_state.expected_items)[['Barcode', 'Product Name']], use_container_width=True)

                st.markdown("#### 2. Scan สินค้า")
                if not st.session_state.prod_val:
                    col1, col2 = st.columns([3, 1])
                    manual_prod = col1.text_input("พิมพ์ Barcode", key="pack_prod_man").strip()
                    if manual_prod: st.session_state.prod_val = manual_prod; st.rerun()
                    
                    scan_prod = back_camera_input("สแกนสินค้า", key=f"prod_cam_{st.session_state.cam_counter}")
                    if scan_prod:
                        res_p = decode(Image.open(scan_prod))
                        if res_p: st.session_state.prod_val = res_p[0].data.decode("utf-8"); st.rerun()
                
                else:
                    scanned = st.session_state.prod_val; found = None
                    for item in st.session_state.expected_items:
                        if str(item.get('Barcode', '')).strip() == scanned: found = item; break
                    
                    if found:
                        if not any(x['Barcode'] == scanned for x in st.session_state.current_order_items):
                            st.session_state.current_order_items.append(found)
                            utils.play_sound('success')
                            
                            # เช็คว่าครบหรือยัง?
                            if len(st.session_state.current_order_items) >= len(st.session_state.expected_items):
                                st.toast(f"✅ ครบแล้ว! กำลังไปหน้าถ่ายรูป...", icon="📸")
                                st.session_state.picking_phase = 'pack'
                                time.sleep(0.5) 
                                st.rerun()
                            else:
                                st.toast(f"✅ เพิ่ม {found.get('Product Name')}", icon="🛒")
                                st.session_state.prod_val = ""
                                st.session_state.cam_counter += 1
                                st.rerun()
                        else: 
                            st.toast("⚠️ สแกนแล้ว", icon="ℹ️")
                            st.session_state.prod_val = ""; st.session_state.cam_counter += 1; st.rerun()
                    else:
                        utils.play_sound('error'); st.error("⛔ สินค้าผิด!"); time.sleep(1); st.session_state.prod_val = ""; st.session_state.cam_counter += 1; st.rerun()

            if st.session_state.current_order_items:
                st.markdown("---")
                st.markdown(f"### 🛒 แพ็คแล้ว ({len(st.session_state.current_order_items)}/{len(st.session_state.expected_items)})")
                st.dataframe(pd.DataFrame(st.session_state.current_order_items)[['Barcode', 'Product Name']], use_container_width=True)
                
                if len(st.session_state.current_order_items) < len(st.session_state.expected_items):
                    st.warning("⚠️ ยังสแกนไม่ครบ")
                else:
                    st.button("✅ ยืนยันครบ (ไปถ่ายรูป)", type="primary", use_container_width=True, on_click=go_to_pack_phase)

    # --- Phase 2: PHOTO & UPLOAD ---
    elif st.session_state.picking_phase == 'pack':
        st.success(f"📦 Tracking: **{st.session_state.order_val}**")
        st.markdown("#### 3. 📸 ถ่ายรูปหลักฐาน")
        
        # 1. แสดงกล้องถ่ายรูป และ ปุ่มอัปโหลดรูป
        remaining_slots = 5 - len(st.session_state.photo_gallery)
        if remaining_slots > 0:
            
            # 1.1 กล้องถ่ายรูป (แตะเพื่อถ่าย)
            pack_img = back_camera_input("แตะเพื่อถ่ายรูป", key=f"pack_cam_fin_{st.session_state.cam_counter}")
            if pack_img:
                img_pil = Image.open(pack_img)
                if img_pil.mode in ("RGBA", "P"): img_pil = img_pil.convert("RGB")
                buf = io.BytesIO(); img_pil.save(buf, format='JPEG', quality=90)
                st.session_state.photo_gallery.append(buf.getvalue())
                st.session_state.cam_counter += 1
                utils.play_sound('scan')
                st.rerun()

            # 1.2 ปุ่มอัปโหลดรูปภาพจากเครื่อง (เลือกได้หลายรูป)
            uploaded_imgs = st.file_uploader(f"หรือ อัปโหลดจากเครื่อง (เลือกได้อีก {remaining_slots} รูป)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, key=f"pack_upload_{st.session_state.cam_counter}")
            
            if uploaded_imgs:
                added_count = 0
                for up_img in uploaded_imgs:
                    # ป้องกันไม่ให้อัปโหลดเกิน 5 รูป
                    if len(st.session_state.photo_gallery) < 5:
                        img_pil = Image.open(up_img)
                        if img_pil.mode in ("RGBA", "P"): img_pil = img_pil.convert("RGB")
                        buf = io.BytesIO(); img_pil.save(buf, format='JPEG', quality=90)
                        st.session_state.photo_gallery.append(buf.getvalue())
                        added_count += 1
                
                # ถ้ารูปถูกเพิ่มเข้าไป ให้รีเฟรชหน้าจอเพื่อโชว์รูป
                if added_count > 0:
                    st.session_state.cam_counter += 1
                    utils.play_sound('scan')
                    st.rerun()
        
        # 2. ปุ่ม Action (แก้ไข / Upload)
        col1, col2 = st.columns(2)
        with col1: 
            if st.button("⬅️ แก้ไข", use_container_width=True): 
                st.session_state.picking_phase = 'scan'; st.session_state.photo_gallery = []; st.rerun()
        
        with col2:
            if len(st.session_state.photo_gallery) > 0:
                upload_placeholder = st.empty() 
                
                if upload_placeholder.button("☁️ Upload", type="primary", use_container_width=True):
                    upload_placeholder.empty() # ซ่อนปุ่มระหว่างโหลด
                    
                    with st.spinner("🚀 Uploading... กรุณารอสักครู่"):
                        srv = utils.authenticate_drive()
                        if srv:
                            fid = utils.get_target_folder_structure(srv, st.session_state.order_val, utils.MAIN_FOLDER_ID)
                            ts = utils.get_thai_ts_filename(); uploaded_ids = []
                            for i, img in enumerate(st.session_state.photo_gallery):
                                fn = f"{st.session_state.order_val}_PACKED_{ts}_{i+1}.jpg"
                                uploaded_ids.append(utils.upload_photo(srv, img, fn, fid))
                            
                            for item in st.session_state.current_order_items:
                                utils.save_log_to_sheet(st.session_state.current_user_name, st.session_state.order_val, item['Barcode'], item['Product Name'], item.get('Location','-'), '1', st.session_state.current_user_id, uploaded_ids)
                            
                            utils.play_sound('success')
                            st.success("✅ บันทึกสำเร็จ!")
                            time.sleep(1.5)
                            st.session_state.need_reset = True
                            st.rerun()

        # 3. แสดง Gallery รูปที่เตรียม Upload
        if st.session_state.photo_gallery:
            st.divider()
            st.write(f"📷 รูปที่พร้อม Upload ({len(st.session_state.photo_gallery)}/5)")
            cols = st.columns(4)
            for idx, img in enumerate(st.session_state.photo_gallery):
                with cols[idx % 4]: 
                    st.image(img, use_column_width=True)
                    if st.button("ลบ", key=f"del_{idx}"): 
                        st.session_state.photo_gallery.pop(idx); st.rerun()
