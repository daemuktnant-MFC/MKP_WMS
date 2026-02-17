import streamlit as st
import pandas as pd
import gspread
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime, timedelta
import base64
import io
import json
from googleapiclient.errors import HttpError

# --- CONFIGURATION ---
MAIN_FOLDER_ID = '1sZQKOuw4YGazuy4euk4ns7nLr7Zie6cm'
LOG_SHEET_ID = '1tZfX9I6Ntbo-Jf2_rcqBc2QYUrCCCSAx8K4YBkly92c'
ORDER_CHECK_SHEET_ID = '1Om9qwShA3hBQgKJPQNbJgDPInm9AQ2hY5Z8OuOpkF08'

ORDER_DATA_SHEET_NAME = 'Order_Data'
LOG_SHEET_NAME = 'Logs'
RIDER_SHEET_NAME = 'Rider_Logs'
USER_SHEET_NAME = 'User'

# --- SOUND HELPER ---
def play_sound(status='success'):
    sound_files = {'scan': 'beep.mp3', 'success': 'success.mp3', 'error': 'error.mp3'}
    backup_urls = {
        'scan': "https://www.myinstants.com/media/sounds/barcode-scanner-beep-sound.mp3",
        'success': "https://www.myinstants.com/media/sounds/success-sound-effect.mp3",
        'error': "https://www.myinstants.com/media/sounds/error_CDOxCNm.mp3"
    }
    target_file = sound_files.get(status, 'beep.mp3')
    try:
        with open(target_file, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            st.markdown(f"""<audio autoplay><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>""", unsafe_allow_html=True)
    except FileNotFoundError:
        sound_url = backup_urls.get(status, backup_urls['scan'])
        st.markdown(f"""<audio autoplay><source src="{sound_url}" type="audio/mp3"></audio>""", unsafe_allow_html=True)

# --- AUTHENTICATION ---
def get_credentials():
    try:
        if "oauth" in st.secrets:
            info = st.secrets["oauth"]
            return Credentials(None, refresh_token=info["refresh_token"], token_uri="https://oauth2.googleapis.com/token", client_id=info["client_id"], client_secret=info["client_secret"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        else:
            st.error("❌ ไม่พบข้อมูล [oauth] ใน Secrets")
            return None
    except Exception as e:
        st.error(f"❌ Error Credentials: {e}"); return None

def authenticate_drive():
    try:
        creds = get_credentials()
        if creds: return build('drive', 'v3', credentials=creds)
        return None
    except Exception as e:
        st.error(f"Error Drive: {e}"); return None

# --- DATA LOADING ---
@st.cache_data(ttl=600)
def load_sheet_data(sheet_name, spreadsheet_key):
    try:
        creds = get_credentials()
        if not creds: return pd.DataFrame()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(spreadsheet_key)
        try:
            if isinstance(sheet_name, int): worksheet = sh.get_worksheet(sheet_name)
            else: worksheet = sh.worksheet(sheet_name)
        except: return pd.DataFrame()
        
        rows = worksheet.get_all_values()
        if len(rows) > 1:
            headers = rows[0]; data = rows[1:]
            seen = {}; unique_headers = []
            for col in headers:
                clean_col = col.strip()
                if not clean_col: clean_col = "Untitled"
                if clean_col in seen: seen[clean_col] += 1; unique_headers.append(f"{clean_col}_{seen[clean_col]}")
                else: seen[clean_col] = 0; unique_headers.append(clean_col)
            df = pd.DataFrame(data, columns=unique_headers)
            for col in df.columns:
                col_lower = col.lower()
                if 'tracking' in col_lower or ('order' in col_lower and 'id' in col_lower): df.rename(columns={col: 'Tracking'}, inplace=True)
                elif 'barcode' in col_lower: df.rename(columns={col: 'Barcode'}, inplace=True); df['Barcode'] = df['Barcode'].astype(str).str.replace(r'\.0$', '', regex=True)
                elif col == 'Name' or 'product name' in col_lower: df.rename(columns={col: 'Product Name'}, inplace=True)
                elif 'qty' in col_lower or 'quantity' in col_lower: df.rename(columns={col: 'Qty'}, inplace=True)
            return df
        return pd.DataFrame()
    except Exception as e: st.error(f"❌ Load Error: {e}"); return pd.DataFrame()

# --- TIME & HELPERS ---
def get_thai_time(): return (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
def get_thai_ts_filename(): return (datetime.utcnow() + timedelta(hours=7)).strftime("%Y%m%d_%H%M%S")

# --- SAVE LOGIC ---
def save_log_to_sheet(picker_name, order_id, barcode, prod_name, location, pick_qty, user_col, file_id_or_list):
    try:
        creds = get_credentials(); gc = gspread.authorize(creds); sh = gc.open_by_key(LOG_SHEET_ID)
        try: worksheet = sh.worksheet(LOG_SHEET_NAME)
        except: worksheet = sh.add_worksheet(title=LOG_SHEET_NAME, rows="1000", cols="20"); worksheet.append_row(["Timestamp", "Picker Name", "Order ID", "Barcode", "Product Name", "Location", "Pick Qty", "User", "Image Link"])
        timestamp = get_thai_time()
        if isinstance(file_id_or_list, list): image_link = "\n".join([f"https://drive.google.com/open?id={fid}" for fid in file_id_or_list])
        else: image_link = f"https://drive.google.com/open?id={file_id_or_list}"
        worksheet.append_row([timestamp, picker_name, order_id, barcode, prod_name, location, pick_qty, user_col, image_link])
    except Exception as e: st.warning(f"⚠️ Save Log Error: {e}")

# --- DRIVE UPLOAD ---
def upload_photo(service, file_obj, filename, folder_id):
    try:
        file_metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_obj) if isinstance(file_obj, bytes) else file_obj, mimetype='image/jpeg', chunksize=1024*1024, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e: raise e

def get_target_folder_structure(service, order_id, main_parent_id):
    now = datetime.utcnow() + timedelta(hours=7); date_str = now.strftime("%d-%m-%Y"); year_str = now.strftime("%Y"); month_str = now.strftime("%m")
    def _get_or_create(parent_id, name):
        q = f"name = '{name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res = service.files().list(q=q, fields="files(id)").execute(); files = res.get('files', [])
        if files: return files[0]['id']
        meta = {'name': name, 'parents': [parent_id], 'mimeType': 'application/vnd.google-apps.folder'}
        folder = service.files().create(body=meta, fields='id').execute(); return folder.get('id')
    year_id = _get_or_create(main_parent_id, year_str); month_id = _get_or_create(year_id, month_str); date_id = _get_or_create(month_id, date_str)
    order_folder_name = f"{order_id}_{now.strftime('%H-%M')}"
    meta_order = {'name': order_folder_name, 'parents': [date_id], 'mimeType': 'application/vnd.google-apps.folder'}
    order_folder = service.files().create(body=meta_order, fields='id').execute(); return order_folder.get('id')
