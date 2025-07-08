import streamlit as st

def check_login(username, password):
    return (
        username == st.secrets["login"]["username"]
        and password == st.secrets["login"]["password"]
    )

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

st.set_page_config(page_title="Login", layout="centered")
st.title("🔐 Lemon Lab Login")

with st.form("login_form"):
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_btn = st.form_submit_button("Login")

    if login_btn:
        if check_login(username.strip(), password.strip()):
            st.session_state.logged_in = True
            st.success("Login successful! Redirecting...")
            st.switch_page("app.py")  # 🔁 This is the magic
        else:
            st.error("❌ Invalid credentials")
