import os
import tempfile
import shutil
import streamlit as st
from folder_uploader import process_folder
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd
import psycopg2

# Load environment variables
load_dotenv()

st.set_page_config(page_title="Mouse Data System", layout="wide")
st.title("🐭 Mouse Experiment Database Portal")

# Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# DB connection
def get_db_connection():
    import streamlit as st
    import psycopg2
    return psycopg2.connect(
        host=st.secrets["host"],
        dbname=st.secrets["dbname"],
        user=st.secrets["user"],
        password=st.secrets["password"],
        port=st.secrets["port"]
    )

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

# -------- Tabs --------
tab1, tab2 = st.tabs(["📤 Upload Data", "📂 View Database"])

# -------- Upload Tab --------
with tab1:
    with st.form("upload_form"):
        uploader = st.text_input("Uploader Name*")
        description = st.text_area("Experiment Description*")
        zip_file = st.file_uploader("Upload ZIP*", type=["zip"])

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
                        st.error("No valid experiment folder found.")
                        st.stop()

                    with st.spinner("Processing..."):
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
                    st.error(f"Critical error: {str(e)}")

# -------- View Tab --------
with tab2:
    st.subheader("Database Tables")
    table = st.selectbox("Select table to view", [
        "experiments", "rigs", "exp_groups", "mice", "training_folders", "days", "files"
    ])

    try:
        conn = get_db_connection()
        df = pd.read_sql(f"SELECT * FROM {table} ORDER BY 1 DESC", conn)
        st.dataframe(df, use_container_width=True)
        conn.close()
    except Exception as e:
        st.error(f"❌ Failed to fetch data: {str(e)}")
