import streamlit as st
import utils
import gspread

def add_user(uid, upass, uname, urole):
    try:
        creds = utils.get_credentials(); gc = gspread.authorize(creds); sh = gc.open_by_key(utils.ORDER_CHECK_SHEET_ID); ws = sh.worksheet(utils.USER_SHEET_NAME)
        exist = ws.col_values(1); clean_ex = [str(x).lower().strip() for x in exist]
        if str(uid).lower().strip() in clean_ex: return False, "❌ ID ซ้ำ"
        ws.append_row([uid, upass, uname, urole]); utils.load_sheet_data.clear(); return True, "✅ เพิ่มสำเร็จ"
    except Exception as e: return False, str(e)

def del_user(uid):
    try:
        creds = utils.get_credentials(); gc = gspread.authorize(creds); sh = gc.open_by_key(utils.ORDER_CHECK_SHEET_ID); ws = sh.worksheet(utils.USER_SHEET_NAME)
        cell = ws.find(str(uid))
        if cell: ws.delete_rows(cell.row); utils.load_sheet_data.clear(); return True, "✅ ลบสำเร็จ"
        return False, "❌ ไม่พบ ID"
    except Exception as e: return False, str(e)

def app():
    st.title("👥 จัดการพนักงาน")
    df = utils.load_sheet_data(utils.USER_SHEET_NAME, utils.ORDER_CHECK_SHEET_ID)
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("➕ เพิ่ม")
        nid = st.text_input("ID", key="n_id"); nname = st.text_input("Name", key="n_name")
        npass = st.text_input("Pass", key="n_pass", type="password"); nrole = st.selectbox("Role", ["staff", "admin"])
        if st.button("บันทึก"):
            if nid and nname and npass:
                ok, msg = add_user(nid, npass, nname, nrole)
                if ok: st.success(msg); st.rerun()
                else: st.error(msg)
    
    with c2:
        st.subheader("🗑️ ลบ")
        if not df.empty:
            opts = df.apply(lambda x: f"{x.iloc[0]}: {x.iloc[2]}", axis=1).tolist()
            sel = st.selectbox("เลือก", opts)
            if st.button("ยืนยันลบ"):
                ok, msg = del_user(sel.split(":")[0])
                if ok: st.success(msg); st.rerun()
                else: st.error(msg)
    
    st.divider()
    st.dataframe(df, use_container_width=True)
