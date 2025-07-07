import streamlit as st

from urllib.parse import urlencode
import os, tempfile, shutil
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client
from folder_uploader import process_folder, get_db_connection

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Login function
def check_login(input_user, input_pass):
    try:
        return (
            input_user == st.secrets["login"]["username"]
            and input_pass == st.secrets["login"]["password"]
        )
    except Exception:
        return False

# Session state + rerun trick
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

query_params = st.experimental_get_query_params()

if not st.session_state.logged_in:
    st.subheader("🔐 Please log in to continue")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Login")

    if login_btn:
        if check_login(username.strip(), password.strip()):
            st.session_state.logged_in = True
            st.success("✅ Login successful! Redirecting...")
            st.experimental_set_query_params(logged="true")
            st.stop()
        else:
            st.error("❌ Invalid credentials.")

    st.stop()

# Move these below login to avoid lag
st.set_page_config(page_title="Data Management", layout="wide")
st.title("Lemon Lab Data Portal")
