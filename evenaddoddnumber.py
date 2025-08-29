# app.py
import streamlit as st
import sqlite3
import os
from passlib.hash import bcrypt
import pyotp
import time
import uuid
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

# Load environment variables (TWILIO, PAYSTACK etc) from .env when present
load_dotenv()

# ----------------------------
# Configuration & Constants
# ----------------------------
DB_PATH = "lovable_bank.db"
OTP_EXPIRY_SECONDS = 300  # 5 minutes
MAX_DAILY_REWARDS = 5000

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_FROM = os.getenv("TWILIO_FROM")

PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")
FLUTTERWAVE_SECRET = os.getenv("FLUTTERWAVE_SECRET")

# ----------------------------
# DB Setup
# ----------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    # users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        phone TEXT UNIQUE,
        email TEXT,
        name TEXT,
        nin TEXT,
        bvn TEXT,
        pin_hash BLOB,
        totp_secret TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    # wallet table
    c.execute("""
    CREATE TABLE IF NOT EXISTS wallets (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        balance INTEGER DEFAULT 0,
        currency TEXT DEFAULT 'NGN',
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    # transactions
    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        type TEXT,
        amount INTEGER,
        status TEXT,
        metadata TEXT,
        created_at TEXT
    )
    """)
    # otp table
    c.execute("""
    CREATE TABLE IF NOT EXISTS otps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        otp TEXT,
        created_at REAL
    )
    """)
    # savings goals
    c.execute("""
    CREATE TABLE IF NOT EXISTS savings (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        name TEXT,
        target INTEGER,
        saved INTEGER DEFAULT 0,
        frequency TEXT,
        created_at TEXT
    )
    """)
    # support tickets
    c.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        subject TEXT,
        message TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ----------------------------
# Helpers
# ----------------------------
# Hash a PIN
hashed_pin = bcrypt.hash("1234")

# Verify a PIN
if bcrypt.verify("1234", hashed_pin):
    print("PIN correct")
else:
    print("Wrong PIN")

def create_user(phone, name=None, email=None, nin=None, bvn=None, pin=None, is_admin=0):
    conn = get_conn()
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    pin_hash = hash_pin(pin) if pin else None
    c.execute("INSERT INTO users (id, phone, email, name, nin, bvn, pin_hash, is_admin, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
              (user_id, phone, email, name, nin, bvn, pin_hash, is_admin, now))
    # create wallet
    wallet_id = str(uuid.uuid4())
    c.execute("INSERT INTO wallets (id, user_id, balance) VALUES (?,?,?)", (wallet_id, user_id, 0))
    conn.commit()
    conn.close()
    return user_id

def find_user_by_phone(phone):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    r = c.fetchone()
    conn.close()
    return r

def get_wallet(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r

def update_wallet_balance(user_id, delta_amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE wallets SET balance = balance + ? WHERE user_id = ?", (delta_amount, user_id))
    conn.commit()
    conn.close()

def log_transaction(user_id, ttype, amount, status="success", metadata=""):
    conn = get_conn()
    c = conn.cursor()
    tid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO transactions (id, user_id, type, amount, status, metadata, created_at) VALUES (?,?,?,?,?,?,?)",
              (tid, user_id, ttype, amount, status, metadata, now))
    conn.commit()
    conn.close()
    return tid

# ----------------------------
# OTP Handling (mock + Twilio support)
# ----------------------------
def send_otp(phone):
    # generate 6-digit OTP
    otp = f"{int.from_bytes(os.urandom(3), 'big') % 1000000:06d}"
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO otps (phone, otp, created_at) VALUES (?,?,?)", (phone, otp, time.time()))
    conn.commit()
    conn.close()

    # If Twilio credentials present, you can integrate real SMS sending here.
    if TWILIO_SID and TWILIO_AUTH and TWILIO_FROM:
        try:
            # Real sending (example using Twilio REST API via requests or twilio SDK)
            payload = {
                "To": phone,
                "From": TWILIO_FROM,
                "Body": f"Your OTP is {otp}. It expires in {OTP_EXPIRY_SECONDS//60} minutes."
            }
            # PLACEHOLDER: implement Twilio request here or use twilio python SDK
            # requests.post(twilio_url, auth=(TWILIO_SID, TWILIO_AUTH), data=payload)
            pass
        except Exception as e:
            st.warning("Real SMS sending failed; OTP stored in DB for dev use.")
    # For development we return or show the OTP
    return otp

def verify_otp(phone, otp_input):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT otp, created_at FROM otps WHERE phone = ? ORDER BY created_at DESC LIMIT 1", (phone,))
    r = c.fetchone()
    conn.close()
    if not r:
        return False, "No OTP found. Request a new one."
    otp, created_at = r
    if time.time() - created_at > OTP_EXPIRY_SECONDS:
        return False, "OTP expired."
    if otp_input == otp:
        return True, "OTP verified"
    return False, "OTP incorrect"

# ----------------------------
# TOTP 2FA helpers
# ----------------------------
def generate_totp_secret():
    return pyotp.random_base32()

def verify_totp(secret, code):
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except Exception:
        return False

# ----------------------------
# Payment stub & fraud stub
# ----------------------------
def process_payment(user_id, amount, provider="paystack", metadata=None):
    """
    This function is a stub. Replace with real API calls to Paystack/Flutterwave.
    It should:
    - create a payment reference
    - redirect or open checkout for the user
    - verify via webhook or direct verify endpoint
    - upon success, credit user's wallet and log transaction
    """
    reference = str(uuid.uuid4())
    log_transaction(user_id, f"fund_{provider}", amount, status="pending", metadata=reference)
    # Simulate immediate success for demo
    update_wallet_balance(user_id, amount)
    # update tx status
    log_transaction(user_id, f"fund_{provider}_complete", amount, status="success", metadata=reference)
    return {"status": "success", "reference": reference}

def fraud_check(user_id, amount, action="transfer"):
    """
    Very simple fraud stub. Extend with:
    - device fingerprint
    - velocity checks
    - geolocation checks
    - heuristic scoring
    """
    wallet = get_wallet(user_id)
    if wallet and wallet["balance"] < amount and action == "withdraw":
        return False, "Insufficient balance"
    # add more rules...
    return True, "OK"

# ----------------------------
# Support ticketing helpers
# ----------------------------
def create_ticket(user_id, subject, message):
    conn = get_conn()
    c = conn.cursor()
    tid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO tickets (id, user_id, subject, message, status, created_at) VALUES (?,?,?,?,?,?)",
              (tid, user_id, subject, message, "open", now))
    conn.commit()
    conn.close()
    return tid

# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="Lovable Bank - Demo", layout="wide")
st.title("💜 Lovable Bank — Streamlit Demo")

menu = st.sidebar.selectbox("Navigation", ["Landing", "Payment", "Transactions", "Admin", "Support"])

# session state
if "auth_user" not in st.session_state:
    st.session_state["auth_user"] = None
if "auth_phone" not in st.session_state:
    st.session_state["auth_phone"] = None

# ----------------------------
# Landing Page
# ----------------------------
if menu == "Landing":
    st.header("Welcome to Lovable Bank")
    st.write("Sign up or log in to manage wallet, pay bills, save, and play games.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Register")
        reg_phone = st.text_input("Phone (e.g. +2348012345678)", key="reg_phone")
        reg_name = st.text_input("Full name", key="reg_name")
        reg_nin = st.text_input("NIN (optional)", key="reg_nin")
        reg_bvn = st.text_input("BVN (optional)", key="reg_bvn")
        reg_pin = st.text_input("Choose 4-digit PIN", type="password", key="reg_pin")
        if st.button("Request OTP & Register"):
            if not reg_phone or not reg_pin:
                st.error("Phone and PIN required")
            else:
                otp = send_otp(reg_phone)
                st.session_state["pending_registration"] = {
                    "phone": reg_phone,
                    "name": reg_name,
                    "nin": reg_nin,
                    "bvn": reg_bvn,
                    "pin": reg_pin
                }
                st.success("OTP sent (for demo the OTP is printed below).")
                st.info(f"DEV OTP: {otp}")

        if "pending_registration" in st.session_state:
            reg_otp_input = st.text_input("Enter OTP to complete registration", key="reg_otp")
            if st.button("Complete Registration"):
                pdata = st.session_state["pending_registration"]
                ok, msg = verify_otp(pdata["phone"], reg_otp_input)
                if ok:
                    existing = find_user_by_phone(pdata["phone"])
                    if existing:
                        st.error("Phone already registered. Please login.")
                    else:
                        uid = create_user(pdata["phone"], pdata["name"], nin=pdata["nin"], bvn=pdata["bvn"], pin=pdata["pin"])
                        st.success("Registration complete. You can now log in.")
                        del st.session_state["pending_registration"]
                else:
                    st.error(msg)

    with col2:
        st.subheader("Login")
        login_phone = st.text_input("Phone", key="login_phone")
        login_pin = st.text_input("PIN", type="password", key="login_pin")
        use_bio = st.checkbox("Use device biometric (simulate)", key="login_bio")

        if st.button("Login"):
            user = find_user_by_phone(login_phone)
            if not user:
                st.error("Phone not found. Please register.")
            else:
                if use_bio:
                    # Simulated biometric: allow if account exists
                    st.session_state["auth_user"] = user["id"]
                    st.session_state["auth_phone"] = login_phone
                    st.success("Biometric auth simulated: logged in.")
                else:
                    if not user["pin_hash"]:
                        st.error("User has no PIN set.")
                    else:
                        if check_pin(login_pin, user["pin_hash"]):
                            # if user has TOTP enabled, require it
                            if user["totp_secret"]:
                                st.session_state["pending_totp_user"] = user["id"]
                                st.info("This account has 2FA enabled. Enter your TOTP code on the Payment page.")
                            else:
                                st.session_state["auth_user"] = user["id"]
                                st.session_state["auth_phone"] = login_phone
                                st.success("Logged in successfully.")
                        else:
                            st.error("Incorrect PIN.")

        st.markdown("---")
        st.write("If you forgot your PIN, request an OTP to reset it.")
        forgot_phone = st.text_input("Phone for PIN reset", key="forgot_phone")
        if st.button("Send reset OTP"):
            otp = send_otp(forgot_phone)
            st.info(f"DEV OTP: {otp}")
            st.session_state["pin_reset_phone"] = forgot_phone

        if "pin_reset_phone" in st.session_state:
            reset_otp = st.text_input("Enter OTP to reset PIN", key="reset_otp")
            new_pin = st.text_input("New 4-digit PIN", type="password", key="new_pin")
            if st.button("Reset PIN"):
                ok, msg = verify_otp(st.session_state["pin_reset_phone"], reset_otp)
                if ok:
                    user = find_user_by_phone(st.session_state["pin_reset_phone"])
                    if user:
                        conn = get_conn()
                        c = conn.cursor()
                        c.execute("UPDATE users SET pin_hash = ? WHERE id = ?", (hash_pin(new_pin), user["id"]))
                        conn.commit()
                        conn.close()
                        st.success("PIN reset complete.")
                        del st.session_state["pin_reset_phone"]
                    else:
                        st.error("Phone not registered.")
                else:
                    st.error(msg)

# ----------------------------
# Payment Page (Dashboard)
# ----------------------------
elif menu == "Payment":
    st.header("Payment / Dashboard")
    if not st.session_state.get("auth_user"):
        st.info("You must login first on the Landing page.")
    else:
        uid = st.session_state["auth_user"]
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (uid,))
        user = c.fetchone()
        wallet = get_wallet(uid)
        st.subheader(f"Hello, {user['name'] or user['phone']}")
        st.metric("Wallet Balance", f"₦{wallet['balance'] / 100:.2f}")

        # Quick actions
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("### Send Money")
            send_to = st.text_input("Recipient phone", key="send_to")
            send_amt = st.number_input("Amount (NGN)", min_value=0.0, format="%.2f", key="send_amt")
            if st.button("Send"):
                # convert to kobo as integer
                amt_kobo = int(send_amt * 100)
                ok, reason = fraud_check(uid, amt_kobo, action="transfer")
                if not ok:
                    st.error(f"Blocked: {reason}")
                else:
                    recipient = find_user_by_phone(send_to)
                    if not recipient:
                        st.error("Recipient not found.")
                    else:
                        # deduct and credit
                        update_wallet_balance(uid, -amt_kobo)
                        update_wallet_balance(recipient["id"], amt_kobo)
                        log_transaction(uid, "transfer_out", amt_kobo, status="success", metadata=f"to:{send_to}")
                        log_transaction(recipient["id"], "transfer_in", amt_kobo, status="success", metadata=f"from:{user['phone']}")
                        st.success("Transfer complete.")

        with col2:
            st.markdown("### Fund Wallet")
            fund_amount = st.number_input("Amount to add (NGN)", min_value=0.0, format="%.2f", key="fund_amount")
            if st.button("Fund Wallet"):
                amt_kobo = int(fund_amount * 100)
                # call payment provider
                res = process_payment(uid, amt_kobo, provider="paystack")
                if res["status"] == "success":
                    st.success("Wallet funded successfully (demo).")
                else:
                    st.error("Funding failed.")

            st.markdown("---")
            st.markdown("### Savings")
            sg_name = st.text_input("Goal name", key="sg_name")
            sg_target = st.number_input("Target amount (NGN)", min_value=0.0, format="%.2f", key="sg_target")
            if st.button("Create Savings Goal"):
                if not sg_name or sg_target <= 0:
                    st.error("Enter valid goal name and target.")
                else:
                    conn = get_conn()
                    c = conn.cursor()
                    sid = str(uuid.uuid4())
                    now = datetime.utcnow().isoformat()
                    c.execute("INSERT INTO savings (id, user_id, name, target, saved, frequency, created_at) VALUES (?,?,?,?,?,?,?)",
                              (sid, uid, sg_name, int(sg_target*100), 0, "monthly", now))
                    conn.commit()
                    st.success("Savings goal created.")

        with col3:
            st.markdown("### Play & Win (Games)")
            st.write("Mini-games to win wallet credits (demo).")
            if st.button("Spin & Win"):
                # simple spinner reward: random small amount
                reward = (int.from_bytes(os.urandom(2), "big") % 5000) + 50  # in kobo
                # cap daily reward in real app
                update_wallet_balance(uid, reward)
                log_transaction(uid, "game_reward", reward, status="success", metadata="spin")
                st.success(f"You won ₦{reward/100:.2f}!")

            if st.button("Trivia (Demo)"):
                # demo: always small reward
                reward = 100  # kobo
                update_wallet_balance(uid, reward)
                log_transaction(uid, "game_reward", reward, status="success", metadata="trivia")
                st.success(f"You won ₦{reward/100:.2f}!")

        # 2FA setup
        st.markdown("---")
        st.subheader("Security & 2FA")
        if not user["totp_secret"]:
            if st.button("Enable TOTP 2FA (Google Authenticator)"):
                secret = generate_totp_secret()
                conn = get_conn()
                c = conn.cursor()
                c.execute("UPDATE users SET totp_secret = ? WHERE id = ?", (secret, uid))
                conn.commit()
                st.write("TOTP enabled. Add this secret to your authenticator app:")
                st.code(secret)
                st.info("Scan QR in production UI; here you get the secret for demo.")
        else:
            st.write("2FA Enabled. Enter code to verify session.")
            code = st.text_input("TOTP Code", key="totp_code")
            if st.button("Verify 2FA"):
                if verify_totp(user["totp_secret"], code):
                    st.success("2FA code valid.")
                    st.session_state["auth_user"] = uid
                else:
                    st.error("Invalid code.")

# ----------------------------
# Transactions Page
# ----------------------------
elif menu == "Transactions":
    st.header("Transactions")
    if not st.session_state.get("auth_user"):
        st.info("Login required.")
    else:
        uid = st.session_state["auth_user"]
        conn = get_conn()
        c = conn.cursor()
        filters = st.multiselect("Filter types", ["transfer_in","transfer_out","fund_paystack","fund_paystack_complete","game_reward","savings_deposit","loan_disburse"], default=[])
        q = "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC"
        c.execute(q, (uid,))
        rows = c.fetchall()
        for r in rows:
            ttype = r["type"]
            if filters and ttype not in filters:
                continue
            st.write(f"{r['created_at']} • {ttype} • ₦{r['amount']/100:.2f} • {r['status']}")
            if st.button(f"Details {r['id']}", key=f"tx_{r['id']}"):
                st.json(dict(r))

# ----------------------------
# Support Page
# ----------------------------
elif menu == "Support":
    st.header("Support")
    if not st.session_state.get("auth_user"):
        st.info("Login required.")
    else:
        uid = st.session_state["auth_user"]
        sub = st.text_input("Subject")
        msg = st.text_area("Message")
        if st.button("Open Ticket"):
            tid = create_ticket(uid, sub, msg)
            st.success(f"Ticket created: {tid}")

        st.markdown("### My tickets")
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC", (uid,))
        trows = c.fetchall()
        for t in trows:
            st.write(f"{t['created_at']} • {t['subject']} • {t['status']}")
            if st.button(f"View {t['id']}", key=f"ticket_{t['id']}"):
                st.write(t["message"])

# ----------------------------
# Admin Page
# ----------------------------
elif menu == "Admin":
    st.header("Admin Dashboard")
    # simple admin auth
    admin_pwd = st.text_input("Admin password", type="password", key="admin_pwd")
    if st.button("Unlock Admin"):
        # Very simple admin check: ensure there is at least one admin user seeded,
        # for demo we allow any password and show admin tools (replace with real auth)
        # In prod: require proper auth + role checks
        st.session_state["is_admin"] = True

    if st.session_state.get("is_admin"):
        st.subheader("Users")
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id, phone, name, nin, bvn, created_at FROM users ORDER BY created_at DESC")
        users = c.fetchall()
        for u in users:
            st.write(f"{u['created_at']} • {u['phone']} • {u['name']} • NIN:{u['nin']} BVN:{u['bvn']}")
            if st.button(f"Make Admin {u['id']}", key=f"make_admin_{u['id']}"):
                conn = get_conn()
                c = conn.cursor()
                c.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (u['id'],))
                conn.commit()
                st.success("Updated.")

        st.subheader("Pending transactions (demo)")
        c.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT 20")
        txs = c.fetchall()
        for tx in txs:
            st.write(dict(tx))

        st.subheader("Configure system (stubs)")
        st.write("Payment providers, fees, alerts, loan configs would be set here in production.")
        st.info("This admin UI is a simple demo. Build a full admin panel for production.")

# ----------------------------
# End of app
# ----------------------------
st.markdown("---")
st.caption("Demo app — not for production. Follow security best practices before going live.")

