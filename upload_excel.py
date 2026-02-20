import streamlit as st
import pandas as pd
import utils
import gspread
import time

def app():
    st.title("📤 อัปโหลดข้อมูล Order (Excel)")
    st.info("อัปโหลดไฟล์ Excel เพื่อรวมข้อมูล ค้นหา Barcode อัตโนมัติ และอัปเดตลงในแท็บ Order_Data")

    # อัปโหลดได้หลายไฟล์
    uploaded_files = st.file_uploader("เลือกไฟล์ Excel (เลือกพร้อมกันได้หลายไฟล์)", type=['xlsx', 'xls'], accept_multiple_files=True)

    if uploaded_files:
        st.markdown("---")
        st.subheader(f"📋 ไฟล์ที่รออัปโหลด ({len(uploaded_files)} ไฟล์)")
        
        # 1. แสดงรายชื่อไฟล์ที่รอ Upload ทั้งหมดให้เห็นชัดเจน
        for i, file in enumerate(uploaded_files):
            st.write(f"{i+1}. {file.name}")
            
        st.write("") # เว้นบรรทัด
        
        # เริ่มกระบวนการเตรียมข้อมูลทันทีเพื่อแสดงให้ดูก่อน
        with st.spinner("กำลังเตรียมข้อมูลและดึง Barcode..."):
            try:
                # อ่านและรวมไฟล์ทั้งหมด
                dfs = []
                for file in uploaded_files:
                    file.seek(0) # รีเซ็ตการอ่านไฟล์
                    df = pd.read_excel(file)
                    dfs.append(df)
                
                main_df = pd.concat(dfs, ignore_index=True)
                
                # โหลดข้อมูล SKU
                df_sku = utils.load_sheet_data('SKU', utils.ORDER_CHECK_SHEET_ID)
                sku_dict = {}
                if not df_sku.empty:
                    tesco_col = [c for c in df_sku.columns if 'tescosku' in c.lower().replace(' ', '')]
                    barcode_col = [c for c in df_sku.columns if 'barcode' in c.lower().replace(' ', '')]
                    if tesco_col and barcode_col:
                        t_col, b_col = tesco_col[0], barcode_col[0]
                        for _, row in df_sku.iterrows():
                            t_sku = str(row[t_col]).strip()
                            b_code = str(row[b_col]).strip()
                            if t_sku.endswith('.0'): t_sku = t_sku[:-2]
                            if b_code.endswith('.0'): b_code = b_code[:-2]
                            sku_dict[t_sku] = b_code

                # จับคู่ Barcode
                main_tesco_col = [c for c in main_df.columns if 'tescosku' in str(c).lower().replace(' ', '')]
                if main_tesco_col:
                    tc = main_tesco_col[0]
                    def get_barcode(val):
                        v_str = str(val).strip()
                        if v_str.endswith('.0'): v_str = v_str[:-2]
                        return sku_dict.get(v_str, "ไม่พบข้อมูล SKU")
                    main_df['Barcode'] = main_df[tc].apply(get_barcode)
                else:
                    st.warning("⚠️ ไม่พบคอลัมน์ 'TescoSKU' ในไฟล์ Excel")
                    main_df['Barcode'] = ""
                
                # ย้าย Barcode มาหน้าสุด (Column A)
                cols = main_df.columns.tolist()
                cols.remove('Barcode')
                cols = ['Barcode'] + cols
                main_df = main_df[cols]
                main_df = main_df.fillna("")

                # 2. แสดงตัวอย่างข้อมูลให้ดูก่อนกดอัปโหลด
                st.success(f"✅ พร้อมอัปโหลด! รวมข้อมูลได้ทั้งหมด **{len(main_df)}** แถว")
                st.dataframe(main_df, use_container_width=True)

            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")
                st.stop() # หยุดการทำงานถ้ารวมไฟล์ไม่ได้

        # 3. ปุ่มอัปโหลดจะปรากฏอยู่ด้านล่างสุด หลังจากเห็นข้อมูลแล้ว
        if st.button("🚀 ยืนยันการอัปโหลดขึ้น Google Sheet", type="primary", use_container_width=True):
            with st.spinner("กำลังบันทึกลง Google Sheet..."):
                try:
                    creds = utils.get_credentials()
                    gc = gspread.authorize(creds)
                    sh = gc.open_by_key(utils.ORDER_CHECK_SHEET_ID)
                    
                    try:
                        worksheet = sh.worksheet(utils.ORDER_DATA_SHEET_NAME)
                    except:
                        worksheet = sh.add_worksheet(title=utils.ORDER_DATA_SHEET_NAME, rows="1000", cols="20")
                    
                    worksheet.clear()
                    data_to_upload = [main_df.columns.values.tolist()] + main_df.values.tolist()
                    worksheet.update(values=data_to_upload, range_name="A1")
                    st.cache_data.clear() # เคลียร์แคชเพื่อให้แอปส่วนอื่นเห็นข้อมูลใหม่
                    
                    st.success("🎉 อัปโหลดสำเร็จเรียบร้อยแล้ว!")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดตอนอัปโหลด: {e}")
