import os
import tempfile
import shutil
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client
from folder_uploader import process_folder, get_db_connection

# -------------------------------
# ⚙️ Page Config
# -------------------------------
st.set_page_config(page_title="Data Management", layout="wide")

# -------------------------------
# 🔐 Secrets-based Login + Access Key
# -------------------------------
def check_login(username, password):
    return (
        username == st.secrets["login"]["username"]
        and password == st.secrets["login"]["password"]
    )

def check_access_key(input_key):
    return input_key == st.secrets["viewer"]["access_key"]

# -------------------------------
# 🔐 Session State Init
# -------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "access_granted" not in st.session_state:
    st.session_state.access_granted = False

# -------------------------------
# 🔐 Login UI
# -------------------------------
if not st.session_state.logged_in:
    st.title("Lemon Lab Data Portal")
    st.subheader("🔐 Please log in to continue")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if check_login(username.strip(), password.strip()):
                st.session_state.logged_in = True
            else:
                st.error("❌ Invalid username or password.")
    st.stop()

# -------------------------------
# ✅ Main App (Post Login)
# -------------------------------
st.title("Lemon Lab Data Portal")

# 🔁 Logout
st.sidebar.title("Session")
if st.sidebar.button("🚪 Logout"):
    for key in st.session_state.keys():
        del st.session_state[key]
    st.experimental_rerun()

# Load env
load_dotenv()

# Supabase init
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Utility: Clean system files
def clean_system_files(root_path):
    for root, dirs, files in os.walk(root_path, topdown=False):
        for name in dirs + files:
            if name.startswith(('.', '__')):
                path = os.path.join(root, name)
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)

def get_experiment_root(tmpdir):
    items = [item for item in os.listdir(tmpdir)
             if not item.startswith(('.', '_')) and os.path.isdir(os.path.join(tmpdir, item))]
    return os.path.join(tmpdir, items[0]) if items else None

# Tabs
tab1, tab2 = st.tabs(["📤 Upload Data", "📂 View Database"])

# -------------------------
# 📤 Upload Tab
# -------------------------
with tab1:
    with st.form("upload_form"):
        uploader = st.text_input("Uploader Name*", max_chars=100)
        description = st.text_area("Experiment Description*", max_chars=500)
        zip_file = st.file_uploader("Upload Zipped Folder*", type=["zip"])
        if st.form_submit_button("Upload Data"):
            if not all([uploader.strip(), description.strip(), zip_file]):
                st.warning("Please fill in all required fields.")
                st.stop()

            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    zip_path = os.path.join(tmpdir, zip_file.name)
                    with open(zip_path, "wb") as f:
                        f.write(zip_file.getbuffer())
                    shutil.unpack_archive(zip_path, tmpdir)

                    clean_system_files(tmpdir)
                    exp_path = get_experiment_root(tmpdir)
                    if not exp_path:
                        st.error("❌ No valid experiment folder found.")
                        st.stop()

                    with st.spinner("Processing and uploading..."):
                        success = process_folder(
                            root_path=exp_path,
                            supabase=supabase,
                            uploader=uploader.strip(),
                            experiment_description=description.strip()
                        )
                        if success:
                            st.success("✅ Upload successful!")
                        else:
                            st.error("❌ Upload failed. See error above.")
                except Exception as e:
                    st.error(f"🚨 Critical error: {str(e)}")

# -------------------------
# 📂 View Tab (Access Key Protected)
# -------------------------
with tab2:
    st.subheader("🔐 Secure Database Viewer")

    if not st.session_state.access_granted:
        with st.form("access_form"):
            key_input = st.text_input("Enter access key", type="password")
            key_submit = st.form_submit_button("Unlock Viewer")
            if key_submit:
                if check_access_key(key_input.strip()):
                    st.session_state.access_granted = True
                else:
                    st.error("❌ Incorrect access key.")
        st.stop()

    # Access granted: show DB
    table = st.selectbox("Select table to view", [
        "experiments", "rigs", "exp_groups", "mice", "training_folders", "days", "files"
    ])
    try:
        conn = get_db_connection()
        df = pd.read_sql(f"SELECT * FROM {table} ORDER BY 1 DESC", conn)
        conn.close()
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"❌ Failed to fetch data: {str(e)}")
