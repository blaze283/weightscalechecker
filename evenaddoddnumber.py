# money_matters_full.py
import streamlit as st
import sqlite3
import datetime as dt
from forex_python.converter import CurrencyRates
import qrcode
from io import BytesIO
import requests
import json
import os

# -------------------- CONFIG --------------------
st.set_page_config(page_title="Money Matters", page_icon="💰", layout="wide")
LOCAL_CURRENCY = "NGN"
DB_PATH = "money_matters.db"
PARENT_DEFAULT_PASSWORD = "parent123"   # change in production

# -------------------- UTIL: DB --------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # users table: phone is primary key; role is 'kid' or 'parent'
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        phone TEXT PRIMARY KEY,
        name TEXT,
        role TEXT,         -- 'kid' or 'parent'
        pin TEXT,          -- simple PIN/password (hashed? store plaintext for demo; replace with hash in prod)
        linked_parent TEXT, -- parent's phone (nullable)
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS accounts (
        phone TEXT PRIMARY KEY,  -- same as users.phone
        balance REAL DEFAULT 0,
        goal_name TEXT DEFAULT '',
        goal_amount REAL DEFAULT 0,
        stars INTEGER DEFAULT 0,
        badges TEXT DEFAULT '[]',
        daily_limit REAL DEFAULT 500.0,
        spent_today REAL DEFAULT 0.0,
        last_spending_reset TEXT,
        allowance_amt REAL DEFAULT 0.0,
        allowance_freq TEXT DEFAULT '',
        allowance_last_paid TEXT
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        ts TEXT,
        type TEXT,
        amount REAL,
        currency TEXT,
        converted REAL
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        ts TEXT,
        message TEXT,
        read INTEGER DEFAULT 0
    );
    """)
    conn.commit()
    return conn

init_db()
conn = get_conn()

# -------------------- UTIL: Currency --------------------
def get_currency_service():
    try:
        return CurrencyRates()
    except Exception:
        return None

c = get_currency_service()
DEMO_RATES = {"USD": 1600.0, "EUR": 1700.0, "GBP": 2000.0, "NGN": 1.0}

def convert_to_local(amount: float, from_code: str) -> float:
    from_code = from_code.upper()
    if from_code == LOCAL_CURRENCY:
        return float(amount)
    if c is None:
        rate = DEMO_RATES.get(from_code, 1500.0)
        return float(amount) * rate
    return float(c.convert(from_code, LOCAL_CURRENCY, amount))

# -------------------- UTIL: QR --------------------
def make_qr(data: str) -> bytes:
    img = qrcode.make(data)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# -------------------- AUTH / USER --------------------
def user_exists(phone):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE phone = ?", (phone,))
    return cur.fetchone() is not None

def create_user(phone, name, role, pin, linked_parent=None):
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users (phone,name,role,pin,linked_parent,created_at) VALUES (?,?,?,?,?,?)",
                (phone, name, role, pin, linked_parent, dt.datetime.now().isoformat()))
    # create account row if missing
    cur.execute("INSERT OR IGNORE INTO accounts (phone, last_spending_reset) VALUES (?, ?)", (phone, dt.date.today().isoformat()))
    conn.commit()

def authenticate(phone, pin):
    cur = conn.cursor()
    cur.execute("SELECT pin FROM users WHERE phone = ?", (phone,))
    row = cur.fetchone()
    if row and row["pin"] == pin:
        return True
    return False

def get_user(phone):
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    return cur.fetchone()

def get_account(phone):
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE phone = ?", (phone,))
    row = cur.fetchone()
    return dict(row) if row else None

def update_account(phone, **kwargs):
    keys = []
    vals = []
    for k, v in kwargs.items():
        keys.append(f"{k} = ?")
        vals.append(v)
    vals.append(phone)
    cur = conn.cursor()
    cur.execute(f"UPDATE accounts SET {', '.join(keys)} WHERE phone = ?", vals)
    conn.commit()

def add_transaction(phone, tx_type, amount, currency, converted):
    cur = conn.cursor()
    cur.execute("INSERT INTO transactions (phone,ts,type,amount,currency,converted) VALUES (?,?,?,?,?,?)",
                (phone, dt.datetime.now().isoformat(), tx_type, float(amount), currency, float(converted)))
    conn.commit()

def get_transactions(phone, limit=100):
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE phone = ? ORDER BY id DESC LIMIT ?", (phone, limit))
    return cur.fetchall()

def add_notification(phone, message):
    cur = conn.cursor()
    cur.execute("INSERT INTO notifications (phone,ts,message,read) VALUES (?,?,?,0)", (phone, dt.datetime.now().isoformat(), message))
    conn.commit()

def get_notifications(phone, only_unread=False):
    cur = conn.cursor()
    if only_unread:
        cur.execute("SELECT * FROM notifications WHERE phone = ? AND read = 0 ORDER BY id DESC", (phone,))
    else:
        cur.execute("SELECT * FROM notifications WHERE phone = ? ORDER BY id DESC", (phone,))
    return cur.fetchall()

def mark_notifications_read(phone):
    cur = conn.cursor()
    cur.execute("UPDATE notifications SET read = 1 WHERE phone = ?", (phone,))
    conn.commit()

# -------------------- OTP (SIMULATED) --------------------
# Replace send_otp_sms with real SMS API (Twilio, Africa's Talking, etc.) in production
otp_store = {}  # phone -> otp (ephemeral; it's OK for demo)
def generate_otp(phone):
    import random
    code = f"{random.randint(100000, 999999)}"
    otp_store[phone] = code
    return code

def send_otp_sms(phone, code):
    # Simulation: show code in UI, but in production send SMS using provider
    # e.g., Twilio / Africa's Talking / Fast2SMS
    # For now we just store it and present to the user in a note.
    add_notification(phone, f"[SIM] OTP sent: {code}")  # also add a notification
    return True

# -------------------- EXTERNAL TRANSFERS HELPERS --------------------
def flutterwave_available():
    return "flutterwave" in st.secrets and "secret_key" in st.secrets["flutterwave"]

def kora_available():
    return "kora" in st.secrets and "api_key" in st.secrets["kora"]

def send_flutterwave_transfer(amount, acct_no, bank_code, reference):
    if not flutterwave_available():
        # simulate success
        return {"status": "success", "message": "Simulated Flutterwave transfer (no keys)"}
    url = "https://api.flutterwave.com/v3/transfers"
    headers = {"Authorization": f"Bearer {st.secrets['flutterwave']['secret_key']}"}
    payload = {
        "account_bank": bank_code,
        "account_number": acct_no,
        "amount": amount,
        "currency": LOCAL_CURRENCY,
        "narration": "Money Matters Transfer",
        "reference": reference,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def send_kora_palmpay(amount, recipient_id, reference):
    if not kora_available():
        return {"status": "success", "message": "Simulated Kora Palmpay (no keys)"}
    url = "https://api.korahq.com/payouts"
    headers = {"Authorization": f"Bearer {st.secrets['kora']['api_key']}"}
    payload = {
        "recipient_type": "palmpay",
        "recipient_id": recipient_id,
        "amount": amount,
        "currency": LOCAL_CURRENCY,
        "reference": reference,
        "narration": "Money Matters Transfer",
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------- APP STATE --------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "login_phone" not in st.session_state:
    st.session_state.login_phone = None
if "role" not in st.session_state:
    st.session_state.role = None

# -------------------- UI: Header --------------------
st.title("💳 Money Matters — Kid Banking (Phone = Account)")

# -------------------- NAV --------------------
menu = ["Home", "Sign Up", "Log In", "Parent Mode", "Admin (DB)"]
choice = st.sidebar.selectbox("Navigation", menu)

# -------------------- HOME --------------------
def page_home():
    st.header("Welcome to Money Matters")
    st.write("An easy kid-friendly banking app. Sign up with a phone number (this is the account number).")
    if st.session_state.logged_in:
        st.success(f"Logged in as {st.session_state.login_phone} ({st.session_state.role})")
        acct = get_account(st.session_state.login_phone)
        if acct:
            st.metric("Balance", f"{acct['balance']:.2f} {LOCAL_CURRENCY}")
            st.write("Quick actions below.")
    else:
        st.info("You are not logged in. Please Sign Up or Log In from the sidebar.")

# -------------------- SIGN UP --------------------
def page_signup():
    st.header("Sign Up (Phone = Account)")
    with st.form("signup_form"):
        phone = st.text_input("Phone number (e.g. +2348012345678)").strip()
        name = st.text_input("Full name")
        role = st.selectbox("Role", ["kid", "parent"])
        pin = st.text_input("Choose a 4-6 digit PIN (for demo only)", type="password")
        parent_phone = None
        if role == "kid":
            parent_phone = st.text_input("Parent's phone number (to link account) - optional")
        submitted = st.form_submit_button("Request OTP")
    if submitted:
        if not phone or not pin or not name:
            st.error("phone, name and pin are required")
            return
        # Generate OTP and 'send'
        code = generate_otp(phone)
        send_otp_sms(phone, code)
        st.info("OTP generated and simulated sent. Enter the code to complete signup below.")
        st.session_state["pending_signup"] = {"phone": phone, "name": name, "role": role, "pin": pin, "parent_phone": parent_phone}

    if "pending_signup" in st.session_state:
        ps = st.session_state.pending_signup
        code_in = st.text_input("Enter OTP (simulated)")
        if st.button("Verify & Create Account"):
            if otp_store.get(ps["phone"]) == code_in:
                # create user & account
                create_user(ps["phone"], ps["name"], ps["role"], ps["pin"], ps["parent_phone"])
                st.success("Account created! You can now log in.")
                del st.session_state["pending_signup"]
                if ps["role"] == "kid" and ps["parent_phone"]:
                    add_notification(ps["parent_phone"], f"Child account created and linked: {ps['name']} ({ps['phone']})")
            else:
                st.error("Invalid OTP")

# -------------------- LOGIN --------------------
def page_login():
    st.header("Log In")
    phone = st.text_input("Phone number (account)")
    pin = st.text_input("PIN", type="password")
    if st.button("Log In"):
        if authenticate(phone, pin):
            st.session_state.logged_in = True
            st.session_state.login_phone = phone
            st.session_state.role = get_user(phone)["role"]
            st.success(f"Logged in as {phone}")
        else:
            st.error("Wrong phone or PIN")

# -------------------- PARENT MODE --------------------
def page_parent_mode():
    st.header("Parent / Kid Dashboard")
    if not st.session_state.logged_in:
        st.warning("Please log in first.")
        return
    phone = st.session_state.login_phone
    user = get_user(phone)
    if user["role"] == "kid":
        st.info("You're logged in as a kid. Parents must log in to parent mode.")
    # show parent controls if parent
    if user["role"] == "parent":
        st.subheader("Parent Controls")
        # list linked kids
        cur = conn.cursor()
        cur.execute("SELECT phone,name FROM users WHERE linked_parent = ?", (phone,))
        linked = cur.fetchall()
        st.write("Linked child accounts:")
        for r in linked:
            st.write(f"- {r['name']} ({r['phone']})")
        # create child
        with st.form("create_child"):
            child_phone = st.text_input("Child phone")
            child_name = st.text_input("Child name")
            child_pin = st.text_input("Child PIN", type="password")
            create_ok = st.form_submit_button("Create child account and link")
        if create_ok:
            if user_exists(child_phone):
                st.error("Phone already used")
            else:
                create_user(child_phone, child_name, "kid", child_pin, linked_parent=phone)
                st.success("Child created and linked")
        st.markdown("---")
        # parent can pick a child to manage
        all_children = [r["phone"] for r in linked]
        if all_children:
            pick = st.selectbox("Manage child", all_children)
            acct = get_account(pick)
            st.metric("Balance", f"{acct['balance']:.2f} {LOCAL_CURRENCY}")
            # add pocket money
            add_amt = st.number_input("Add pocket money (NGN)", min_value=0.0, step=50.0, key="parent_add")
            if st.button("Add pocket money"):
                if add_amt > 0:
                    newbal = acct["balance"] + add_amt
                    update_account(pick, balance=newbal)
                    add_transaction(pick, "Parent Deposit", add_amt, LOCAL_CURRENCY, add_amt)
                    add_notification(pick, f"Parent added pocket money: +{add_amt:.2f} {LOCAL_CURRENCY}")
                    st.success("Pocket money added")
            # set allowance and daily limit
            alw_amt = st.number_input("Allowance amount", min_value=0.0, step=50.0, value=acct["allowance_amt"], key="alw_amt")
            alw_freq = st.selectbox("Allowance frequency", ["None","Daily","Weekly","Monthly"], index=0 if not acct["allowance_freq"] else ["None","Daily","Weekly","Monthly"].index(acct["allowance_freq"]), key="alw_freq")
            dlimit = st.number_input("Daily spending limit (NGN)", min_value=0.0, step=50.0, value=acct["daily_limit"], key="dlimit")
            if st.button("Save child settings"):
                update_account(pick, allowance_amt=alw_amt, allowance_freq=(None if alw_freq=="None" else alw_freq), daily_limit=dlimit)
                st.success("Settings saved")
        # view notifications
        st.markdown("---")
        st.subheader("Parent Dashboard: All Kids Overview")
        cur.execute("SELECT * FROM accounts")
        rows = cur.fetchall()
        for r in rows:
            st.write(f"{r['phone']}: Balance {r['balance']:.2f} NGN | daily_limit {r['daily_limit']:.2f} | allowance {r['allowance_amt'] or 0}")
    else:
        # kid view
        st.subheader("Kid Controls")
        acct = get_account(phone)
        st.metric("Balance", f"{acct['balance']:.2f} {LOCAL_CURRENCY}")
        st.write(f"Daily limit: {acct['daily_limit']:.2f} | Spent today: {acct['spent_today']:.2f}")

        # deposit (kid side) - multi-currency
        with st.form("kid_deposit"):
            amt = st.number_input("Deposit amount", min_value=1.0, step=1.0)
            ccy = st.text_input("Currency code (USD, EUR...)", value="USD")
            dep_ok = st.form_submit_button("Deposit")
        if dep_ok:
            try:
                converted = convert_to_local(amt, ccy)
                newbal = acct["balance"] + converted
                update_account(phone, balance=newbal)
                add_transaction(phone, "Deposit", amt, ccy.upper(), converted)
                # rewards
                stars = acct["stars"] + (1 if converted<1000 else 3 if converted<5000 else 5)
                update_account(phone, stars=stars)
                if len(get_transactions(phone, limit=1000)) == 1:
                    b = json.loads(acct["badges"])
                    if "Starter Saver" not in b:
                        b.append("Starter Saver")
                        update_account(phone, badges=json.dumps(b))
                st.success(f"Deposited {amt} {ccy.upper()} = {converted:.2f} {LOCAL_CURRENCY}")
            except Exception as e:
                st.error("Deposit failed: " + str(e))

# -------------------- LOGGED-IN USER PAGES --------------------
def kid_dashboard():
    phone = st.session_state.login_phone
    user = get_user(phone)
    acct = get_account(phone)
    st.header(f"{user['name']} — Account: {phone} (Kid)")
    # reset spent_today if date changed
    today = dt.date.today().isoformat()
    if acct["last_spending_reset"] != today:
        update_account(phone, spent_today=0.0, last_spending_reset=today)

    # show quick metrics
    st.metric("Balance", f"{acct['balance']:.2f} {LOCAL_CURRENCY}")
    st.write(f"Daily limit: {acct['daily_limit']:.2f} | Spent today: {acct['spent_today']:.2f}")

    # notifications
    with st.expander("🔔 Notifications"):
        notes = get_notifications(phone)
        if notes:
            for n in notes:
                read_mark = " (read)" if n["read"] else ""
                st.write(f"{n['ts']}: {n['message']}{read_mark}")
            if st.button("Mark notifications as read"):
                mark_notifications_read(phone)
        else:
            st.write("No notifications")

    # deposit/withdraw
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Deposit (any currency)")
        dep_amt = st.number_input("Amount", min_value=1.0, step=1.0, key="d_amt")
        dep_ccy = st.text_input("Currency code", "USD", key="d_ccy")
        if st.button("Deposit Now"):
            try:
                converted = convert_to_local(dep_amt, dep_ccy)
                newbal = acct["balance"] + converted
                update_account(phone, balance=newbal)
                add_transaction(phone, "Deposit", dep_amt, dep_ccy.upper(), converted)
                st.success(f"Deposited {dep_amt} {dep_ccy.upper()} = {converted:.2f} {LOCAL_CURRENCY}")
            except Exception as e:
                st.error("Deposit failed: " + str(e))
    with col2:
        st.subheader("Spend / Withdraw")
        w_amt = st.number_input("Withdraw (NGN)", min_value=1.0, step=1.0, key="w_amt2")
        if st.button("Spend / Withdraw"):
            if w_amt > acct["balance"]:
                st.error("Not enough balance")
            elif acct["daily_limit"] > 0 and acct["spent_today"] + w_amt > acct["daily_limit"]:
                st.error("Daily spending limit reached")
            else:
                newbal = acct["balance"] - w_amt
                new_spent = acct["spent_today"] + w_amt
                update_account(phone, balance=newbal, spent_today=new_spent)
                add_transaction(phone, "Withdrawal", w_amt, LOCAL_CURRENCY, w_amt)
                st.success("Spent/Withdrawn: " + str(w_amt))

    st.markdown("---")
    # QR P2P: generate and scan
    st.subheader("P2P QR Payments")
    qr_tab1, qr_tab2 = st.tabs(["Generate QR to Receive", "Scan QR to Send"])
    with qr_tab1:
        req_amt = st.number_input("Request amount (NGN)", min_value=1.0, step=1.0, key="req_amt2")
        if st.button("Generate QR"):
            qrdata = f"PAYTO:{phone}:{req_amt}"
            img = make_qr(qrdata)
            st.image(img, width=220)
            st.download_button("Download QR", img, file_name=f"{phone}_pay_qr.png", mime="image/png")
    with qr_tab2:
        qr_input = st.text_input("Paste QR text here (e.g., PAYTO:+234801...:200)")
        send_amount = st.number_input("Amount to send (NGN)", min_value=1.0, step=1.0, key="send_amt")
        if st.button("Send via QR"):
            if not qr_input.startswith("PAYTO:"):
                st.error("Invalid QR format")
            else:
                try:
                    _, recv_phone, amt_s = qr_input.split(":")
                    amt = float(amt_s)
                    if amt > acct["balance"]:
                        st.error("Not enough balance")
                    else:
                        # check daily limit
                        if acct["daily_limit"] > 0 and acct["spent_today"] + amt > acct["daily_limit"]:
                            st.error("Daily spending limit reached")
                        else:
                            # debit sender
                            newbal = acct["balance"] - amt
                            new_spent = acct["spent_today"] + amt
                            update_account(phone, balance=newbal, spent_today=new_spent)
                            add_transaction(phone, "Sent via QR", amt, LOCAL_CURRENCY, amt)
                            # credit receiver
                            if not user_exists(recv_phone):
                                st.error("Receiver phone not found")
                            else:
                                r_acct = get_account(recv_phone)
                                r_newbal = r_acct["balance"] + amt
                                update_account(recv_phone, balance=r_newbal)
                                add_transaction(recv_phone, "Received via QR", amt, LOCAL_CURRENCY, amt)
                                add_notification(recv_phone, f"Received {amt:.2f} {LOCAL_CURRENCY} from {phone} via QR")
                                st.success(f"Sent {amt:.2f} to {recv_phone}")
                except Exception as e:
                    st.error("Send failed: " + str(e))

    st.markdown("---")
    # savings goal
    st.subheader("Savings Goal")
    gname = st.text_input("Goal name", acct["goal_name"], key="gname")
    gamt = st.number_input("Goal amount (NGN)", min_value=0.0, step=100.0, value=acct["goal_amount"], key="gamt")
    if st.button("Set Goal"):
        update_account(phone, goal_name=gname, goal_amount=gamt)
        st.success("Goal updated")
    if acct["goal_amount"] > 0:
        progress = min(acct["balance"] / acct["goal_amount"], 1.0) if acct["goal_amount"] else 0
        st.progress(progress)
        st.write(f"Saved {acct['balance']:.2f} / {acct['goal_amount']:.2f}")
        if progress >= 1.0:
            st.balloons()
            add_notification(phone, f"Goal achieved: {acct['goal_name']}")

    st.markdown("---")
    # external transfer (requires parent approval)
    st.subheader("Transfer to External Bank or Palmpay (Requires Parent Approval)")
    st.info("This action will create a transfer request that a parent must approve in their Parent Mode.")
    ext_type = st.selectbox("Destination", ["Bank Account (Flutterwave)", "Palmpay (via Kora)"])
    ext_amt = st.number_input("Amount (NGN)", min_value=1.0, step=100.0, key="ext_amt")
    if ext_type.startswith("Bank"):
        ext_bank_code = st.text_input("Bank code (e.g., 044)")
        ext_acc = st.text_input("Destination account number")
    else:
        ext_palmpay_id = st.text_input("Palmpay recipient ID / phone")
    if st.button("Request External Transfer"):
        # create a pending transaction by notifying parent(s)
        parent_phone = get_user(phone)["linked_parent"]
        if not parent_phone:
            st.error("No linked parent — external transfers require a parent account linked.")
        else:
            # record a "Requested" transaction record with type "External Request"
            add_transaction(phone, "External Transfer Request", ext_amt, LOCAL_CURRENCY, ext_amt)
            add_notification(parent_phone, f"External transfer request from {phone}: {ext_amt:.2f} NGN — approve in Parent Mode")
            st.success("Transfer request sent to parent for approval.")

# -------------------- ADMIN / DB page --------------------
def page_admin():
    st.header("Admin / Database viewer")
    st.write("Use this only for debugging.")
    st.write("Users table:")
    cur = conn.cursor()
    cur.execute("SELECT phone,name,role,linked_parent,created_at FROM users")
    rows = cur.fetchall()
    st.table([dict(r) for r in rows])
    st.write("Accounts table:")
    cur.execute("SELECT * FROM accounts")
    rows = cur.fetchall()
    st.table([dict(r) for r in rows])
    st.write("Transactions (last 50):")
    cur.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 50")
    rows = cur.fetchall()
    st.table([dict(r) for r in rows])
    if st.button("Clear test data (CAUTION)"):
        # careful: remove everything (for dev only)
        cur.executescript("DELETE FROM notifications; DELETE FROM transactions; DELETE FROM users; DELETE FROM accounts;")
        conn.commit()
        st.warning("Cleared DB (for dev only). Restart the app.")
        st.stop()

# -------------------- ALLOWANCE PROCESSOR (AUTO) --------------------
# Simple: when app loads, credit allowances if due (Daily/Weekly/Monthly). We mark last paid date on accounts.
def process_allowances_all():
    cur = conn.cursor()
    cur.execute("SELECT phone,allowance_amt,allowance_freq,allowance_last_paid FROM accounts")
    rows = cur.fetchall()
    today = dt.date.today()
    for r in rows:
        if r["allowance_amt"] and r["allowance_amt"] > 0 and r["allowance_freq"]:
            last = r["allowance_last_paid"]
            freq = r["allowance_freq"]
            pay = False
            if not last:
                pay = True
            else:
                try:
                    lastd = dt.date.fromisoformat(last)
                except:
                    lastd = None
                if freq == "Daily":
                    pay = (lastd != today)
                elif freq == "Weekly":
                    pay = (lastd is None) or ((today - lastd).days >= 7)
                elif freq == "Monthly":
                    pay = (lastd is None) or (today.month != lastd.month or today.year != lastd.year)
            if pay:
                # credit
                newbal = get_account(r["phone"])["balance"] + r["allowance_amt"]
                update_account(r["phone"], balance=newbal, allowance_last_paid=today.isoformat())
                add_transaction(r["phone"], f"Allowance ({freq})", r["allowance_amt"], LOCAL_CURRENCY, r["allowance_amt"])
                add_notification(r["phone"], f"Allowance credited: +{r['allowance_amt']:.2f} {LOCAL_CURRENCY}")

# run once at startup
process_allowances_all()

# -------------------- ROUTER --------------------
if choice == "Home":
    page_home()
elif choice == "Sign Up":
    page_signup()
elif choice == "Log In":
    page_login()
elif choice == "Parent Mode":
    if not st.session_state.logged_in:
        st.warning("Please log in first (parent).")
    else:
        # show relevant interface for logged-in role
        user = get_user(st.session_state.login_phone)
        if user["role"] == "parent":
            page_parent_mode()
        else:
            # kid logged in - show kid dashboard
            kid_dashboard()
elif choice == "Admin (DB)":
    page_admin()

# -------------------- FOOTER --------------------
st.markdown("---")
st.caption("Demo app — replace PIN storage with hashing and OTP sending with real SMS for production. Use real Flutterwave/Kora keys for live transfers.")
