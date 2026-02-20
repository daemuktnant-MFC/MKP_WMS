import streamlit as st
import pandas as pd
import utils
import gspread
import time

# ฟังก์ชันไม้ตาย: ทำความสะอาดข้อมูลก่อนเทียบ
def clean_key(val):
    if pd.isna(val): return ""
    s = str(val).strip().lower() 
    if s.endswith('.0'): s = s[:-2]
    return s

def app():
    st.title("📤 อัปโหลดข้อมูล Order (Excel)")
    st.info("ระบบจะเทียบ 'Tesco SKU' จากไฟล์ Excel กับชีต 'SKU' เพื่อดึง Barcode มาไว้ที่คอลัมน์ A")

    # --- [เพิ่มใหม่] สร้าง Key ไว้รีเซ็ต File Uploader ---
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0

    # ผูก Key เข้ากับ File Uploader
    uploaded_files = st.file_uploader(
        "เลือกไฟล์ Excel (เลือกพร้อมกันได้หลายไฟล์)", 
        type=['xlsx', 'xls'], 
        accept_multiple_files=True,
        key=f"excel_uploader_{st.session_state.uploader_key}" # <--- จุดสำคัญอยู่ตรงนี้
    )

    if uploaded_files:
        st.markdown("---")
        st.subheader(f"📋 ไฟล์ที่รออัปโหลด ({len(uploaded_files)} ไฟล์)")
        
        for i, file in enumerate(uploaded_files):
            st.write(f"{i+1}. {file.name}")
            
        st.write("") 
        
        with st.spinner("กำลังเทียบข้อมูล Tesco SKU และดึง Barcode..."):
            try:
                # 1. อ่านและรวมไฟล์ทั้งหมด
                dfs = []
                for file in uploaded_files:
                    file.seek(0)
                    df = pd.read_excel(file, dtype=str)
                    dfs.append(df)
                
                main_df = pd.concat(dfs, ignore_index=True)
                
                # 2. โหลดข้อมูลชีต "SKU"
                df_sku = utils.load_sheet_data('SKU', utils.ORDER_CHECK_SHEET_ID)
                sku_dict = {}
                t_col_sku = None
                b_col_sku = None
                
                if not df_sku.empty:
                    for c in df_sku.columns:
                        c_clean = str(c).lower().replace(' ', '')
                        if 'tescosku' in c_clean or c_clean == 'sku' or 'tesco' in c_clean: t_col_sku = c
                        if 'barcode' in c_clean: b_col_sku = c
                        
                    if t_col_sku and b_col_sku:
                        for _, row in df_sku.iterrows():
                            k = clean_key(row[t_col_sku])
                            v = str(row[b_col_sku]).strip()
                            if v.endswith('.0'): v = v[:-2] 
                            if k: 
                                sku_dict[k] = v

                # 3. หาคอลัมน์ Tesco SKU ใน Excel ที่อัปโหลดมา
                main_tesco_col = None
                for c in main_df.columns:
                    c_clean = str(c).lower().replace(' ', '')
                    if 'tescosku' in c_clean or c_clean == 'sku' or 'tesco' in c_clean:
                        main_tesco_col = c
                        break
                        
                if main_tesco_col:
                    def map_barcode(val):
                        k = clean_key(val)
                        if not k: return ""
                        return sku_dict.get(k, f"❌ ไม่พบ (ค้นหา:'{k}')")
                        
                    main_df['Barcode_New'] = main_df[main_tesco_col].apply(map_barcode)
                else:
                    st.error(f"❌ ไม่พบคอลัมน์ 'Tesco SKU' ในไฟล์ Excel")
                    main_df['Barcode_New'] = "ไม่พบคอลัมน์อ้างอิง"
                
                # 4. จัดเรียงคอลัมน์
                cols = main_df.columns.tolist()
                cols = [c for c in cols if str(c).lower() not in ['barcode', 'barcode_new']]
                
                main_df.rename(columns={'Barcode_New': 'Barcode'}, inplace=True)
                final_cols = ['Barcode'] + cols
                main_df = main_df[final_cols]
                main_df = main_df.fillna("")

                # 5. สรุปผล
                not_found_count = main_df['Barcode'].astype(str).str.contains('ไม่พบ').sum()
                if not_found_count > 0:
                    st.warning(f"⚠️ พบสินค้าที่ไม่มี Barcode จำนวน **{not_found_count}** รายการ (ดูในช่อง Barcode จะมีแจ้งไว้)")
                else:
                    st.success(f"✅ ดึง Barcode สำเร็จครบทุกรายการ! (ทั้งหมด {len(main_df)} แถว)")
                    
                st.dataframe(main_df, use_container_width=True)

            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการประมวลผล: {e}")
                st.stop() 

        # 6. ปุ่มอัปโหลด
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
                    
                    st.cache_data.clear() 
                    st.success("🎉 อัปโหลดสำเร็จเรียบร้อยแล้ว!")
                    time.sleep(1.5)
                    
                    # --- [เพิ่มใหม่] สั่งอัปเดต Key เพื่อล้างช่องอัปโหลดไฟล์ ---
                    st.session_state.uploader_key += 1
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดตอนอัปโหลด: {e}")
