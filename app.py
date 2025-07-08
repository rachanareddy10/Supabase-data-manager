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
# 🔁 Rerun Trigger After Login
# -------------------------------
if st.session_state.get("rerun_required"):
    st.session_state.rerun_required = False
    st.experimental_rerun()

# -------------------------------
# 🔐 Query Param Login Check
# -------------------------------
params = st.query_params
if params.get("logged_in") == ["true"]:
    st.session_state.logged_in = True

# -------------------------------
# 🔐 Login Function
# -------------------------------
def check_login(input_user, input_pass):
    try:
        return (
            input_user == st.secrets["login"]["username"]
            and input_pass == st.secrets["login"]["password"]
        )
    except Exception:
        return False

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# -------------------------------
# 🔐 Login Form
# -------------------------------
if not st.session_state.logged_in:
    st.title("Lemon Lab Data Portal")
    st.subheader("🔐 Please log in to continue")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Login")

    if login_btn:
        if check_login(username.strip(), password.strip()):
            st.session_state.logged_in = True
            st.session_state.rerun_required = True  # ✅ trigger rerun
            st.query_params.update({"logged_in": "true"})  # ✅ set login param
            st.stop()
        else:
            st.error("❌ Invalid credentials.")
    st.stop()

# -------------------------------
# ✅ Main App (After Login)
# -------------------------------
st.title("Lemon Lab Data Portal")

# 🔁 Logout button
st.sidebar.title("Session")
if st.sidebar.button("🚪 Logout"):
    st.session_state.clear()
    st.query_params.clear()
    st.experimental_rerun()

# Load environment variables
load_dotenv()

# Supabase init
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Utility: Remove system files like .DS_Store, __MACOSX
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

# Tabs: Upload and View
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
                    # Save and unzip
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
# 📂 View Database Tab
# -------------------------
with tab2:
    st.subheader("📋 View Database Tables")
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
