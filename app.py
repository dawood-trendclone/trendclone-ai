# -*- coding: utf-8 -*-
import streamlit as st
import sqlite3
import hashlib
import secrets
import time
import datetime
import smtplib
import os
from email.mime.text import MIMEText

# ========== SECURITY CONFIG ==========
OWNER_EMAIL = "dawoodabdullah256@gmail.com"
ALLOWED_EXTENSIONS = ['mp4', 'mov', 'avi']
MAX_FILE_SIZE = 50 * 1024 * 1024 # 50MB

# ========== DB SETUP ==========
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
    (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, credits INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS complaints
    (id INTEGER PRIMARY KEY, username TEXT, email TEXT, type TEXT, message TEXT, time TEXT, status TEXT)''')
conn.commit()

# ========== SECURITY FUNCTIONS ==========
def hash_password(password):
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return salt + pwd_hash.hex()

def verify_password(stored_password, provided_password):
    salt = stored_password[:32]
    stored_hash = stored_password[32:]
    pwd_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode(), salt.encode(), 100000)
    return pwd_hash.hex() == stored_hash

def check_rate_limit(username):
    if 'login_attempts' not in st.session_state:
        st.session_state.login_attempts = {}
    now = time.time()
    if username not in st.session_state.login_attempts:
        st.session_state.login_attempts[username] = []
    st.session_state.login_attempts[username] = [t for t in st.session_state.login_attempts[username] if now - t < 300]
    if len(st.session_state.login_attempts[username]) >= 5:
        return False
    st.session_state.login_attempts[username].append(now)
    return True

def session_timeout():
    if 'last_activity' in st.session_state:
        if time.time() - st.session_state.last_activity > 1800: # 30 min
            st.session_state.clear()
            st.warning("Session expired. Please login again")
            st.rerun()
    st.session_state.last_activity = time.time()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_email_alert(subject, body):
    try:
        sender = st.secrets["GMAIL_EMAIL"]
        password = st.secrets["GMAIL_APP_PASSWORD"]
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = OWNER_EMAIL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
    except: pass

# ========== LOAD SECRETS ==========
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", "")
TIKTOK_CLIENT_KEY = st.secrets.get("TIKTOK_CLIENT_KEY", "")

# ========== LANDING PAGE ==========
def show_landing():
    st.markdown("""
    <style>.hero {text-align: center; padding: 60px 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 20px;}</style>
    <div class="hero"><h1>⚡ TrendClone AI</h1><p>Turn any video into VIRAL Naruto, Money Heist style in 1 click</p></div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    col1.metric("Time Saved", "3 hours → 10 sec")
    col2.metric("Viral Rate", "87% higher")
    col3.metric("Price", "From $0.30")
    if st.button("🚀 Go to App"): st.session_state.show_app = True; st.rerun()

# ========== MAIN APP ==========
if 'show_app' not in st.session_state:
    show_landing()
else:
    session_timeout()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        tab1, tab2 = st.tabs(["Login", "Register"])
        with tab1:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if not check_rate_limit(username):
                    st.error("Too many attempts. Try again in 5 minutes"); st.stop()
                c.execute("SELECT password FROM users WHERE username=?", (username,))
                result = c.fetchone()
                if result and verify_password(result[0], password):
                    st.session_state.logged_in = True; st.session_state.username = username; st.rerun()
                else: st.error("Wrong username or password")
        with tab2:
            new_user = st.text_input("New Username")
            new_pass = st.text_input("New Password", type="password")
            if st.button("Register"):
                hashed = hash_password(new_pass)
                try:
                    c.execute("INSERT INTO users VALUES (NULL,?,?,?)", (new_user, hashed, 3))
                    conn.commit(); st.success("Account created! 3 free credits")
                except: st.error("Username taken")
    else:
        st.title(f"Welcome {st.session_state.username}")
        st.write("Your app code: Video Generator, Credits, etc")

        uploaded_file = st.file_uploader("Upload Video")
        if uploaded_file:
            if not allowed_file(uploaded_file.name): st.error("Only mp4, mov, avi allowed"); st.stop()
            if uploaded_file.size > MAX_FILE_SIZE: st.error("File too big. Max 50MB"); st.stop()
            st.success("File OK!")

        st.markdown("---")
        with st.form("complain_form"):
            issue_type = st.selectbox("What's the issue?", ["Bug", "Video not generating", "Other"])
            email = st.text_input("Your Email")
            message = st.text_area("Describe the problem")
            if st.form_submit_button("Send Report"):
                c.execute("INSERT INTO complaints VALUES (NULL,?,?,?,?,?,?)",
                    (st.session_state.username, email, issue_type, message, str(datetime.datetime.now()), "Open"))
                conn.commit()
                send_email_alert(f"New {issue_type}", f"From: {email}\n{message}")
                st.success("✅ Report sent!")

        if st.session_state.username == OWNER_EMAIL:
            st.sidebar.title("👑 OWNER PANEL")
            complaints = c.execute("SELECT * FROM complaints ORDER BY time DESC").fetchall()
            for comp in complaints:
                with st.sidebar.expander(f"{comp[3]} - {comp[6]}"):
                    st.write(comp[4])
                    if st.button("Mark Done", key=comp[0]):
                        c.execute("UPDATE complaints SET status='Done' WHERE id=?", (comp[0],)); conn.commit(); st.rerun()

        if st.button("Logout"): st.session_state.clear(); st.rerun()tf-8 -*-
