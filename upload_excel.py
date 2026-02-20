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
        if st.button("🚀 ประมวลผลและอัปโหลด", type="primary", use_container_width=True):
            with st.spinner("กำลังอ่านและประมวลผลข้อมูล..."):
                try:
                    # 1. อ่านและรวมไฟล์ Excel ทั้งหมดเข้าด้วยกัน
                    dfs = []
                    for file in uploaded_files:
                        df = pd.read_excel(file)
                        dfs.append(df)
                    
                    main_df = pd.concat(dfs, ignore_index=True)
                    
                    # 2. โหลดข้อมูลจาก sheet "SKU" เพื่อใช้ทำ Mapping
                    df_sku = utils.load_sheet_data('SKU', utils.ORDER_CHECK_SHEET_ID)
                    
                    # สร้างพจนานุกรมจับคู่ TescoSKU -> Barcode
                    sku_dict = {}
                    if not df_sku.empty:
                        # หาชื่อคอลัมน์โดยไม่สนตัวพิมพ์เล็กใหญ่หรือการเว้นวรรค
                        tesco_col = [c for c in df_sku.columns if 'tescosku' in c.lower().replace(' ', '')]
                        barcode_col = [c for c in df_sku.columns if 'barcode' in c.lower().replace(' ', '')]
                        
                        if tesco_col and barcode_col:
                            t_col, b_col = tesco_col[0], barcode_col[0]
                            for _, row in df_sku.iterrows():
                                t_sku = str(row[t_col]).strip()
                                b_code = str(row[b_col]).strip()
                                # ตัด .0 ทิ้งในกรณีที่ข้อมูลถูกแปลงเป็นทศนิยม
                                if t_sku.endswith('.0'): t_sku = t_sku[:-2]
                                if b_code.endswith('.0'): b_code = b_code[:-2]
                                sku_dict[t_sku] = b_code

                    # 3. จับคู่ Barcode เข้ากับข้อมูล Excel
                    main_tesco_col = [c for c in main_df.columns if 'tescosku' in str(c).lower().replace(' ', '')]
                    
                    if main_tesco_col:
                        tc = main_tesco_col[0]
                        def get_barcode(val):
                            v_str = str(val).strip()
                            if v_str.endswith('.0'): v_str = v_str[:-2]
                            return sku_dict.get(v_str, "ไม่พบข้อมูล SKU")
                        
                        # สร้างคอลัมน์ Barcode ใหม่
                        main_df['Barcode'] = main_df[tc].apply(get_barcode)
                    else:
                        st.warning("⚠️ ไม่พบคอลัมน์ 'TescoSKU' ในไฟล์ Excel (คอลัมน์ Barcode จะว่างเปล่า)")
                        main_df['Barcode'] = ""
                    
                    # 4. จัดเรียงคอลัมน์ให้ Barcode อยู่หน้าสุด (Column A) 
                    # ส่วนข้อมูล Excel เดิมจะถูกเลื่อนไปเริ่มที่ Column B อัตโนมัติ
                    cols = main_df.columns.tolist()
                    cols.remove('Barcode')
                    cols = ['Barcode'] + cols
                    main_df = main_df[cols]
                    
                    # แปลงช่องว่าง (NaN) เป็นสตริงว่าง เพื่อไม่ให้ Google Sheet Error
                    main_df = main_df.fillna("")

                    # 5. อัปโหลดขึ้น Google Sheet
                    st.text("กำลังอัปโหลดข้อมูลไปยัง Google Sheet...")
                    creds = utils.get_credentials()
                    gc = gspread.authorize(creds)
                    sh = gc.open_by_key(utils.ORDER_CHECK_SHEET_ID)
                    
                    # เข้าถึง sheet Order_Data
                    try:
                        worksheet = sh.worksheet(utils.ORDER_DATA_SHEET_NAME)
                    except:
                        worksheet = sh.add_worksheet(title=utils.ORDER_DATA_SHEET_NAME, rows="1000", cols="20")
                    
                    # ล้างข้อมูลเก่าทั้งหมด แล้วเติมข้อมูลใหม่ทับ
                    worksheet.clear()
                    data_to_upload = [main_df.columns.values.tolist()] + main_df.values.tolist()
                    worksheet.update(values=data_to_upload, range_name="A1")
                    
                    # เคลียร์ Cache ของ Streamlit เพื่อให้หน้าแพ็คสินค้าดึงข้อมูลใหม่ทันที
                    st.cache_data.clear()
                    
                    st.success(f"✅ อัปโหลดและจับคู่ Barcode สำเร็จรวม {len(main_df)} รายการ!")
                    time.sleep(2)
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {e}")
