import streamlit as st
import pandas as pd
import utils
import gspread
import time
import re

# ฟังก์ชันช่วยทำความสะอาดข้อความ (ลบช่องว่าง และ .0 ที่เกิดจาก Excel)
def clean_key(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    s = re.sub(r'\.0$', '', s) # ลบ .0 ท้ายสุดทิ้ง
    return s

def app():
    st.title("📤 อัปโหลดข้อมูล Order (Excel)")
    st.info("ระบบจะเทียบ 'Tesco SKU' จากไฟล์ Excel กับชีต 'SKU' เพื่อดึง Barcode มาไว้ที่คอลัมน์ A")

    uploaded_files = st.file_uploader("เลือกไฟล์ Excel (เลือกพร้อมกันได้หลายไฟล์)", type=['xlsx', 'xls'], accept_multiple_files=True)

    if uploaded_files:
        st.markdown("---")
        st.subheader(f"📋 ไฟล์ที่รออัปโหลด ({len(uploaded_files)} ไฟล์)")
        
        for i, file in enumerate(uploaded_files):
            st.write(f"{i+1}. {file.name}")
            
        st.write("") 
        
        with st.spinner("กำลังเทียบข้อมูล Tesco SKU และดึง Barcode..."):
            try:
                # 1. อ่านและรวมไฟล์ทั้งหมด (บังคับให้เป็น String ทั้งหมดแก้ปัญหาทศนิยม .0)
                dfs = []
                for file in uploaded_files:
                    file.seek(0)
                    df = pd.read_excel(file, dtype=str) 
                    dfs.append(df)
                
                main_df = pd.concat(dfs, ignore_index=True)
                
                # 2. โหลดข้อมูลชีต "SKU" เพื่อทำ Dictionary สำหรับค้นหา
                df_sku = utils.load_sheet_data('SKU', utils.ORDER_CHECK_SHEET_ID)
                sku_dict = {}
                
                if not df_sku.empty:
                    # ค้นหาคอลัมน์ Tesco SKU และ Barcode ในชีต SKU
                    t_col = None
                    b_col = None
                    for c in df_sku.columns:
                        c_clean = str(c).lower().replace(' ', '')
                        if 'tescosku' in c_clean: t_col = c
                        if 'barcode' in c_clean: b_col = c
                        
                    if t_col and b_col:
                        for _, row in df_sku.iterrows():
                            t_sku = clean_key(row[t_col])
                            b_code = clean_key(row[b_col])
                            if t_sku: 
                                sku_dict[t_sku] = b_code
                    else:
                        st.warning(f"⚠️ ไม่พบคอลัมน์ Tesco SKU หรือ Barcode ในชีต SKU (พบ: {list(df_sku.columns)})")

                # 3. ค้นหาคอลัมน์ Tesco SKU ในไฟล์ Excel ที่อัปโหลดมา
                main_tesco_col = None
                for c in main_df.columns:
                    if 'tescosku' in str(c).lower().replace(' ', ''):
                        main_tesco_col = c
                        break
                        
                if main_tesco_col:
                    # ทำการ VLOOKUP (Map) ข้อมูล Barcode
                    main_df['Barcode_New'] = main_df[main_tesco_col].apply(lambda x: sku_dict.get(clean_key(x), "ไม่พบข้อมูล SKU"))
                else:
                    st.error(f"❌ ไม่พบคอลัมน์ 'Tesco SKU' ในไฟล์ Excel ที่อัปโหลด (พบ: {list(main_df.columns)})")
                    main_df['Barcode_New'] = "ไม่พบคอลัมน์อ้างอิง"
                
                # 4. จัดเรียงคอลัมน์: เอา Barcode เดิม (ถ้ามี) ออก และย้าย Barcode_New ไปไว้หน้าสุด (Column A)
                cols = main_df.columns.tolist()
                
                # ลบคอลัมน์ชื่อ Barcode หรือ Barcode_New เดิมออกให้หมดเพื่อป้องกัน Error
                cols = [c for c in cols if str(c).lower() not in ['barcode', 'barcode_new']]
                
                # เปลี่ยนชื่อกลับเป็น Barcode และจัดไว้เป็น Column A
                main_df.rename(columns={'Barcode_New': 'Barcode'}, inplace=True)
                final_cols = ['Barcode'] + cols
                main_df = main_df[final_cols]
                
                # แปลงค่าว่างไม่ให้ Google Sheet พัง
                main_df = main_df.fillna("")

                # 5. แสดงผลลัพธ์
                st.success(f"✅ ดึง Barcode สำเร็จ! รวมข้อมูลได้ทั้งหมด **{len(main_df)}** แถว")
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
                    
                    # เคลียร์ข้อมูลเก่าทั้งหมดและวางข้อมูลใหม่
                    worksheet.clear()
                    data_to_upload = [main_df.columns.values.tolist()] + main_df.values.tolist()
                    worksheet.update(values=data_to_upload, range_name="A1")
                    
                    st.cache_data.clear() 
                    st.success("🎉 อัปโหลดสำเร็จเรียบร้อยแล้ว!")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดตอนอัปโหลด: {e}")
