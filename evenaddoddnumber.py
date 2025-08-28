# banking_kids_unified.py
"""
Unified Streamlit app:
 - Adult Banking: register/login using NIN or BVN (provider hooks), wallet, transfer, transactions
 - Kids Savings: parent creates kid account, kid goals, kid requests withdrawal -> parent approves
 - Alerts: Twilio SMS and SMTP email (optional); falls back to in-app logging
 - SQLite persistence for users, wallets, kids, goals, transactions, withdrawals, alerts
"""

import streamlit as st
import sqlite3
import requests
from datetime import datetime, timedelta
import random
import os
import smtplib
from email.mime.text import MIMEText
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# -----------------------
# Config / Secrets
# -----------------------
st.set_page_config(page_title="Unified Banking + Kids Savings", layout="centered")
DB = "banking_unified.db"

# Provider (NIN/BVN) config
PROVIDER = st.secrets.get("PROVIDER", "custom").lower()
PROVIDER_API_KEY = st.secrets.get("PROVIDER_API_KEY", None)
PROVIDER_BASE_URL = st.secrets.get("PROVIDER_BASE_URL", None)

# Twilio (optional)
TWILIO_SID = st.secrets.get("TWILIO_SID", "")
TWILIO_TOKEN = st.secrets.get("TWILIO_TOKEN", "")
TWILIO_FROM = st.secrets.get("TWILIO_FROM", "")

# Email (optional)
EMAIL_HOST = st.secrets.get("EMAIL_HOST", "")
EMAIL_PORT = st.secrets.get("EMAIL_PORT", 465)
EMAIL_USER = st.secrets.get("EMAIL_USER", "")
EMAIL_PASS = st.secrets.get("EMAIL_PASS", "")
EMAIL_FROM = st.secrets.get("EMAIL_FROM", EMAIL_USER)

ph = PasswordHasher()

# -----------------------
# DB init
# -----------------------
def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn):
    cur = conn.cursor()
    # adult users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        nin TEXT,
        bvn TEXT,
        pin_hash TEXT,
        verified INTEGER DEFAULT 0,
        created_at TEXT
    )""")
    # wallets for adult users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS wallets (
        id INTEGER PRIMARY KEY,
        user_id INTEGER UNIQUE NOT NULL,
        balance REAL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    # transactions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        from_user INTEGER,
        to_user INTEGER,
        amount REAL,
        type TEXT,
        note TEXT,
        time TEXT
    )""")
    # kids table (parent-managed)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS kids (
        phone TEXT PRIMARY KEY, -- parent phone used as account id for simplicity
        name TEXT,
        balance REAL DEFAULT 0,
        pin TEXT,
        parent_user_id INTEGER,
        parent_email TEXT
    )""")
    # goals for kids
    cur.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        goal_name TEXT,
        target REAL,
        saved REAL DEFAULT 0
    )""")
    # kid withdrawal requests
    cur.execute("""
    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        amount REAL,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    # alerts log
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alerts_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT,
        recipient TEXT,
        message TEXT,
        time TEXT
    )""")
    # otp table for login fallback
    cur.execute("""
    CREATE TABLE IF NOT EXISTS otps (
        id INTEGER PRIMARY KEY,
        phone TEXT,
        otp TEXT,
        expire_at TEXT,
        used INTEGER DEFAULT 0,
        created_at TEXT
    )""")
    conn.commit()

if not os.path.exists(DB):
    conn = get_db()
    init_db(conn)
else:
    conn = get_db()

# -----------------------
# Utilities
# -----------------------
def now_iso():
    return datetime.utcnow().isoformat()

def log_alert(channel, recipient, message):
    cur = conn.cursor()
    cur.execute("INSERT INTO alerts_log (channel, recipient, message, time) VALUES (?,?,?,?)",
                (channel, recipient, message, now_iso()))
    conn.commit()

# Twilio send (optional)
def send_sms(to_number, message):
    if TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            msg = client.messages.create(body=message, from_=TWILIO_FROM, to=to_number)
            log_alert("sms", to_number, f"SID:{msg.sid} - {message}")
            return True, f"sent ({msg.sid})"
        except Exception as e:
            log_alert("sms", to_number, f"error: {e} - {message}")
            return False, str(e)
    else:
        # fallback: log simulated SMS
        log_alert("sms", to_number, f"(simulated) {message}")
        return True, "simulated (logged)"

# SMTP send (optional)
def send_email(to_email, subject, body):
    if EMAIL_HOST and EMAIL_USER and EMAIL_PASS:
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = EMAIL_FROM or EMAIL_USER
            msg["To"] = to_email
            port = int(EMAIL_PORT) if EMAIL_PORT else 465
            with smtplib.SMTP_SSL(EMAIL_HOST, port, timeout=20) as server:
                server.login(EMAIL_USER, EMAIL_PASS)
                server.sendmail(msg["From"], [to_email], msg.as_string())
            log_alert("email", to_email, f"{subject} - {body}")
            return True, "sent"
        except Exception as e:
            log_alert("email", to_email, f"error: {e} - {subject} - {body}")
            return False, str(e)
    else:
        log_alert("email", to_email, f"(simulated) {subject} - {body}")
        return True, "simulated (logged)"

# OTP helpers
def store_otp(phone, otp, ttl_minutes=10):
    expire_at = (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat()
    cur = conn.cursor()
    cur.execute("INSERT INTO otps (phone, otp, expire_at, used, created_at) VALUES (?,?,?,?,?)",
                (phone, otp, expire_at, 0, now_iso()))
    conn.commit()

def verify_otp(phone, otp):
    cur = conn.cursor()
    cur.execute("SELECT * FROM otps WHERE phone=? AND otp=? AND used=0 ORDER BY id DESC LIMIT 1", (phone, otp))
    row = cur.fetchone()
    if not row:
        return False, "OTP not found"
    if datetime.fromisoformat(row["expire_at"]) < datetime.utcnow():
        return False, "OTP expired"
    cur.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],))
    conn.commit()
    return True, "OK"

# -----------------------
# Adult banking helpers
# -----------------------
def create_adult_user(name, phone, nin=None, bvn=None, pin=None, verified=False):
    cur = conn.cursor()
    pin_hash = ph.hash(pin) if pin else None
    cur.execute("INSERT INTO users (name, phone, nin, bvn, pin_hash, verified, created_at) VALUES (?,?,?,?,?,?,?)",
                (name, phone, nin, bvn, pin_hash, int(verified), now_iso()))
    conn.commit()
    uid = cur.lastrowid
    cur.execute("INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?,?)", (uid, 0.0))
    conn.commit()
    return uid

def get_adult_by_phone(phone):
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone=?", (phone,))
    return cur.fetchone()

def set_balance_user(user_id, amount):
    cur = conn.cursor()
    cur.execute("UPDATE wallets SET balance=? WHERE user_id=?", (float(amount), user_id))
    conn.commit()

def get_balance_user(user_id):
    cur = conn.cursor()
    cur.execute("SELECT balance FROM wallets WHERE user_id=?", (user_id,))
    r = cur.fetchone()
    return float(r["balance"]) if r else 0.0

def add_transaction(from_user, to_user, amount, ttype, note=""):
    cur = conn.cursor()
    cur.execute("INSERT INTO transactions (from_user, to_user, amount, type, note, time) VALUES (?,?,?,?,?,?)",
                (from_user, to_user, float(amount), ttype, note, now_iso()))
    conn.commit()

def get_transactions(user_id):
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE from_user=? OR to_user=? ORDER BY id DESC", (user_id, user_id))
    return cur.fetchall()

# -----------------------
# Kids helpers
# -----------------------
def create_kid_account(parent_user_id, parent_phone, kid_name, parent_pin, parent_email=None):
    # store parent phone as primary key for kid account (simplified model)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO kids (phone, name, balance, pin, parent_user_id, parent_email) VALUES (?,?,?,?,?,?)",
                (parent_phone, kid_name, 0.0, parent_pin, parent_user_id, parent_email))
    conn.commit()

def get_kid(phone):
    cur = conn.cursor()
    cur.execute("SELECT * FROM kids WHERE phone=?", (phone,))
    return cur.fetchone()

def add_money_kid(phone, amount):
    cur = conn.cursor()
    cur.execute("UPDATE kids SET balance = balance + ? WHERE phone=?", (float(amount), phone))
    conn.commit()

def get_kid_balance(phone):
    cur = conn.cursor()
    cur.execute("SELECT balance FROM kids WHERE phone=?", (phone,))
    r = cur.fetchone()
    return float(r["balance"]) if r else 0.0

def create_goal(phone, goal_name, target):
    cur = conn.cursor()
    cur.execute("INSERT INTO goals (phone, goal_name, target, saved) VALUES (?,?,?,0)", (phone, goal_name, float(target)))
    conn.commit()

def get_goals(phone):
    cur = conn.cursor()
    cur.execute("SELECT * FROM goals WHERE phone=?", (phone,))
    return cur.fetchall()

def save_into_goal(goal_id, phone, amount):
    bal = get_kid_balance(phone)
    if amount <= 0 or amount > bal:
        return False
    cur = conn.cursor()
    cur.execute("UPDATE kids SET balance = balance - ? WHERE phone=?", (float(amount), phone))
    cur.execute("UPDATE goals SET saved = saved + ? WHERE id=?", (float(amount), goal_id))
    conn.commit()
    return True

def request_withdrawal(phone, amount):
    cur = conn.cursor()
    cur.execute("INSERT INTO withdrawals (phone, amount, status, created_at) VALUES (?,?, 'pending', ?)",
                (phone, float(amount), now_iso()))
    conn.commit()
    return cur.lastrowid

def get_withdrawals(phone=None, status=None):
    cur = conn.cursor()
    q = "SELECT * FROM withdrawals"
    clauses = []
    params = []
    if phone:
        clauses.append("phone = ?"); params.append(phone)
    if status:
        clauses.append("status = ?"); params.append(status)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY id DESC"
    cur.execute(q, tuple(params))
    return cur.fetchall()

def set_withdrawal(req_id, new_status):
    cur = conn.cursor()
    cur.execute("SELECT phone, amount FROM withdrawals WHERE id=?", (req_id,))
    row = cur.fetchone()
    if not row:
        return False, "Request not found"
    phone, amount = row["phone"], row["amount"]
    if new_status == "approved":
        # check balance
        bal = get_kid_balance(phone)
        if amount > bal:
            return False, "Insufficient kid balance"
        cur.execute("UPDATE kids SET balance = balance - ? WHERE phone=?", (float(amount), phone))
    cur.execute("UPDATE withdrawals SET status=? WHERE id=?", (new_status, req_id))
    conn.commit()
    return True, "OK"

# -----------------------
# Provider adapters (generic)
# -----------------------
def call_provider(url, payload, headers=None):
    if headers is None:
        headers = {}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        return {"status": "success", "raw": r.json()}
    except requests.RequestException as e:
        return {"status": "error", "message": str(e), "raw": None}

def provider_verify_generic(kind, value):
    if not PROVIDER_BASE_URL:
        return {"status": "error", "message": "PROVIDER_BASE_URL not set"}
    headers = {"Authorization": f"Bearer {PROVIDER_API_KEY}"} if PROVIDER_API_KEY else {}
    payload = {kind: value}
    return call_provider(PROVIDER_BASE_URL, payload, headers)

def verify_identity(kind, value):
    # For now call generic adapter; you can replace with provider-specific parsers
    return provider_verify_generic(kind, value)

# -----------------------
# UI: Sidebar and nav
# -----------------------
st.title("Unified Banking + Kids Savings")
st.caption("Adult banking (NIN/BVN) + Kids savings and parent approval. Add provider & Twilio/SMTP keys in .streamlit/secrets.toml")

menu = st.sidebar.selectbox("Section", [
    "Home",
    "Adult Banking: Register/Login",
    "Kids Savings: Register/Login",
    "Admin: Seed / Inspect",
    "Alerts Log",
    "Provider Test"
])

# -----------------------
# Home
# -----------------------
if menu == "Home":
    st.header("Welcome")
    st.write("This app combines adult banking (NIN/BVN verification) and a kids savings flow with parent approval and alerts.")
    st.write("Use the sidebar to choose a section.")

# -----------------------
# Adult Banking
# -----------------------
elif menu == "Adult Banking: Register/Login":
    st.header("Adult Banking — Register")
    with st.form("adult_register"):
        a_name = st.text_input("Full name")
        a_phone = st.text_input("Phone (with country code)")
        a_nin = st.text_input("NIN (optional)")
        a_bvn = st.text_input("BVN (optional)")
        a_pin = st.text_input("Choose a numeric PIN (4+ digits)", type="password")
        submit = st.form_submit_button("Verify & Register")
    if submit:
        if not a_name or not a_phone or not a_pin:
            st.error("Name, phone and PIN required")
        elif not (a_nin or a_bvn):
            st.error("Provide either NIN or BVN")
        else:
            # try verify: call provider
            verified = False
            info = None
            if a_nin:
                st.info("Verifying NIN...")
                res = verify_identity("nin", a_nin.strip())
                if res.get("status") == "success":
                    verified = True
                    info = res.get("raw")
                    st.success("NIN verified")
                else:
                    st.error(f"NIN verify error: {res.get('message')}")
            if (not verified) and a_bvn:
                st.info("Verifying BVN...")
                res = verify_identity("bvn", a_bvn.strip())
                if res.get("status") == "success":
                    verified = True
                    info = res.get("raw")
                    st.success("BVN verified")
                else:
                    st.error(f"BVN verify error: {res.get('message')}")
            if verified:
                if get_adult_by_phone(a_phone.strip()):
                    st.error("Phone already registered")
                else:
                    uid = create_adult_user(a_name.strip(), a_phone.strip(),
                                             nin=a_nin.strip() if a_nin else None,
                                             bvn=a_bvn.strip() if a_bvn else None,
                                             pin=a_pin.strip(), verified=True)
                    # auto-create wallet done in create_adult_user
                    send_sms(a_phone.strip(), f"Welcome {a_name}. Account created (demo).")
                    st.success(f"Account created (id {uid})")
                    if info:
                        st.json(info)

    st.markdown("---")
    st.header("Adult Login")
    a_phone_login = st.text_input("Phone (with country code)", key="adult_login_phone")
    a_pin_login = st.text_input("PIN (optional)", type="password", key="adult_login_pin")
    if st.button("Login (PIN)"):
        user = get_adult_by_phone(a_phone_login.strip())
        if not user:
            st.error("No account")
        else:
            try:
                if ph.verify(user["pin_hash"], a_pin_login.strip()):
                    st.session_state.adult_user_id = user["id"]
                    st.success(f"Welcome back, {user['name']}")
                    st.experimental_rerun()
                else:
                    st.error("Wrong PIN")
            except Exception:
                st.error("PIN verify failed")
    if st.button("Send OTP"):
        if not a_phone_login:
            st.error("Enter phone")
        else:
            otp = str(random.randint(100000, 999999))
            store_otp = store_otp if False else None  # placeholder to avoid lint error
            store_otp(a_phone_login.strip(), otp, ttl_minutes=10)
            send_sms(a_phone_login.strip(), f"Your OTP is {otp}")
            st.success("OTP sent (logged if no Twilio) — use OTP field to login")
    otp_val = st.text_input("OTP (if sent)", key="adult_otp")
    if st.button("Login with OTP"):
        ok, msg = verify_otp(a_phone_login.strip(), otp_val.strip())
        if ok:
            user = get_adult_by_phone(a_phone_login.strip())
            if user:
                st.session_state.adult_user_id = user["id"]
                st.success("Logged in with OTP")
                st.experimental_rerun()
        else:
            st.error(msg)

    # Adult dashboard if logged in
    if st.session_state.get("adult_user_id"):
        uid = st.session_state.adult_user_id
        u = get_adult_by_phone(get_adult_by_phone(uid)["phone"]) if False else None  # safe no-op
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=?", (uid,))
        u = cur.fetchone()
        st.markdown("---")
        st.subheader("Dashboard")
        st.write(f"Name: {u['name']} — Phone: {u['phone']}")
        balance = get_balance_user(uid)
        st.write(f"Balance: ₦{balance:,.2f}")

        c1, c2, c3 = st.columns(3)
        with c1:
            top = st.number_input("Top-up amount", min_value=0.0, value=0.0, key="adult_top")
            if st.button("Top-up"):
                if top > 0:
                    set_balance_user(uid, balance + top)
                    add_transaction(None, uid, top, "deposit", "Top-up")
                    send_sms(u['phone'], f"You were credited ₦{top:.2f}")
                    st.success("Top-up done")
                    st.experimental_rerun()
                else:
                    st.error("Enter amount")
        with c2:
            to_phone = st.text_input("Recipient phone", key="adult_to_phone")
            amt = st.number_input("Amount to send", min_value=0.0, value=0.0, key="adult_send_amt")
            note = st.text_input("Note", key="adult_send_note")
            if st.button("Send"):
                if amt <= 0:
                    st.error("Enter amount")
                elif amt > get_balance_user(uid):
                    st.error("Insufficient funds")
                else:
                    recipient = get_adult_by_phone(to_phone.strip())
                    if not recipient:
                        st.error("Recipient not found")
                    elif not recipient["verified"]:
                        st.error("Recipient not verified")
                    else:
                        set_balance_user(uid, get_balance_user(uid) - amt)
                        set_balance_user(recipient["id"], get_balance_user(recipient["id"]) + amt)
                        add_transaction(uid, recipient["id"], amt, "transfer", note)
                        send_sms(recipient["phone"], f"You received ₦{amt:.2f} from {u['name']}")
                        send_sms(u['phone'], f"You sent ₦{amt:.2f} to {recipient['phone']}")
                        st.success("Transfer done")
                        st.experimental_rerun()
        with c3:
            if st.button("Logout (adult)"):
                del st.session_state["adult_user_id"]
                st.experimental_rerun()

        st.markdown("---")
        st.subheader("Recent transactions")
        txs = get_transactions(uid)
        if txs:
            for t in txs:
                from_p = "SYSTEM" if not t["from_user"] else (get_adult_by_phone(t["from_user"])["phone"] if get_adult_by_phone(t["from_user"]) else "UNKNOWN")
                to_p = "SYSTEM" if not t["to_user"] else (get_adult_by_phone(t["to_user"])["phone"] if get_adult_by_phone(t["to_user"]) else "UNKNOWN")
                st.write(f"[{t['time']}] {t['type']} ₦{t['amount']:.2f} — {t['note']} (from {from_p} to {to_p})")
        else:
            st.info("No transactions yet")

# -----------------------
# Kids Savings
# -----------------------
elif menu == "Kids Savings: Register/Login":
    st.header("Kids Savings — Register (Parent) or Login (Parent/Kid)")
    st.subheader("Register kid (parent creates account)")
    with st.form("kid_register"):
        parent_phone = st.text_input("Parent phone (account id, include country code)")
        kid_name = st.text_input("Kid's name")
        parent_email = st.text_input("Parent email (optional)")
        parent_pin = st.text_input("Parent PIN (used to login as parent)", type="password")
        link_to_adult = st.checkbox("Link this kid account to an existing adult user (by phone)")
        link_phone = st.text_input("Adult user phone to link (optional)", placeholder="+234...")
        submitted = st.form_submit_button("Create kid account")
    if submitted:
        if not parent_phone or not kid_name or not parent_pin:
            st.error("Parent phone, kid name and PIN required")
        else:
            parent_user_id = None
            if link_to_adult and link_phone:
                a = get_adult_by_phone(link_phone.strip())
                parent_user_id = a["id"] if a else None
            create_kid_account(parent_user_id, parent_phone.strip(), kid_name.strip(), parent_pin.strip(), parent_email.strip() if parent_email else None)
            send_sms(parent_phone.strip(), f"{kid_name} account created. Use parent PIN to manage.")
            st.success("Kid account created")

    st.markdown("---")
    st.subheader("Login (Parent or Kid)")
    k_phone = st.text_input("Account phone", key="kid_login_phone")
    k_pin = st.text_input("Parent PIN (leave blank to login as kid)", type="password", key="kid_login_pin")
    if st.button("Login as kid/parent"):
        k = get_kid(k_phone.strip())
        if not k:
            st.error("Account not found")
        else:
            phone_db, name_db, bal_db, pin_db, parent_user_id, parent_email = k
            role = "parent" if (k_pin and k_pin.strip() == pin_db) else "kid"
            st.session_state.kphone = phone_db
            st.session_state.kname = name_db
            st.session_state.krole = role
            st.success(f"Logged in as {name_db} ({role})")

    # if logged in
    if st.session_state.get("kphone"):
        kphone = st.session_state.kphone
        kname = st.session_state.kname
        krole = st.session_state.krole
        st.markdown("---")
        st.header(f"{kname} — {krole.upper()}")
        st.write(f"Balance: ₦{get_kid_balance(kphone):,.2f}")

        if krole == "parent":
            st.subheader("Parent actions")
            top = st.number_input("Top up kid wallet", min_value=0.0, step=50.0)
            if st.button("Add"):
                if top > 0:
                    add_money_kid(kphone, top)
                    send_sms(kphone, f"Wallet credited ₦{top:.2f}")
                    st.success("Top-up done")
                    st.experimental_rerun()
                else:
                    st.error("Enter amount")
            st.markdown("---")
            st.subheader("Pending requests")
            reqs = get_withdrawals(phone=kphone, status="pending")
            if not reqs:
                st.info("No pending requests")
            else:
                for r in reqs:
                    st.write(f"#{r['id']} — ₦{r['amount']:.2f} — {r['created_at']}")
                    c1, c2 = st.columns(2)
                    if c1.button("Approve", key=f"ap_{r['id']}"):
                        ok, msg = set_withdrawal(r['id'], "approved")
                        if ok:
                            send_sms(kphone, f"Withdrawal ₦{r['amount']:.2f} approved")
                            if parent_email:
                                send_email(parent_email, "Withdrawal Approved", f"Withdrawal ₦{r['amount']:.2f} approved for {kname}")
                            st.success("Approved")
                            st.experimental_rerun()
                        else:
                            st.error(msg)
                    if c2.button("Reject", key=f"rej_{r['id']}"):
                        ok, msg = set_withdrawal(r['id'], "rejected")
                        if ok:
                            send_sms(kphone, f"Withdrawal ₦{r['amount']:.2f} rejected")
                            if parent_email:
                                send_email(parent_email, "Withdrawal Rejected", f"Withdrawal ₦{r['amount']:.2f} rejected for {kname}")
                            st.warning("Rejected")
                            st.experimental_rerun()
            st.markdown("---")
            st.subheader("Goals overview")
            goals = get_goals(kphone)
            if not goals:
                st.info("No goals yet")
            else:
                for g in goals:
                    st.write(f"{g['goal_name']}: ₦{g['saved']:.2f} / ₦{g['target']:.2f}")
                    st.progress(min(g['saved']/g['target'] if g['target']>0 else 0, 1.0))
            if st.button("Logout (kid/parent)"):
                for k in ["kphone","kname","krole"]:
                    if k in st.session_state: del st.session_state[k]
                st.experimental_rerun()
        else:
            # kid view
            st.subheader("Savings goals")
            goals = get_goals(kphone)
            if goals:
                for g in goals:
                    st.write(f"{g['id']}: {g['goal_name']} — ₦{g['saved']:.2f} / ₦{g['target']:.2f}")
                    amt = st.number_input(f"Save into {g['goal_name']}", min_value=0.0, step=50.0, key=f"save_{g['id']}")
                    if st.button("Save to goal", key=f"savebtn_{g['id']}"):
                        if save_into_goal(g['id'], kphone, amt):
                            st.success(f"Saved ₦{amt:.2f}")
                            st.experimental_rerun()
                        else:
                            st.error("Not enough balance or invalid amount")
            else:
                st.info("No goals yet")
            st.markdown("---")
            st.subheader("Create goal")
            gname = st.text_input("Goal name", key="kid_new_goal")
            gtarget = st.number_input("Target amount", min_value=50.0, step=50.0, key="kid_target")
            if st.button("Create goal (kid)"):
                if gname and gtarget>0:
                    create_goal(kphone, gname.strip(), float(gtarget))
                    send_sms(kphone, f"Goal '{gname}' created for ₦{gtarget:.2f}")
                    # notify parent
                    k = get_kid(kphone)
                    if k and k["parent_email"]:
                        send_email(k["parent_email"], "New Goal Created", f"{k['name']} created goal '{gname}' target ₦{gtarget:.2f}")
                    st.success("Goal created")
                    st.experimental_rerun()
            st.markdown("---")
            st.subheader("Request withdrawal (parent approval needed)")
            wamt = st.number_input("Amount to request", min_value=0.0, step=50.0, key="kid_req_amt")
            if st.button("Request withdrawal"):
                if wamt <= 0:
                    st.error("Enter amount")
                else:
                    rid = request_withdrawal(kphone, wamt)
                    send_sms(kphone, f"Requested withdrawal ₦{wamt:.2f} (id {rid}) — parent notified")
                    k = get_kid(kphone)
                    if k and k["parent_email"]:
                        send_email(k["parent_email"], "Withdrawal Request", f"{k['name']} requested withdrawal ₦{wamt:.2f}")
                    st.success("Request submitted")
                    st.experimental_rerun()

# -----------------------
# Admin / Inspect
# -----------------------
elif menu == "Admin: Seed / Inspect":
    st.header("Admin tools")
    if st.button("Seed demo adult & kid"):
        if not get_adult_by_phone("+234800000001"):
            create_adult_user("Alice Adult", "+234800000001", nin="12345678901", pin="1234", verified=True)
            uid = get_adult_by_phone("+234800000001")["id"]
            set_balance_user(uid, 500.0)
        if not get_adult_by_phone("+234800000002"):
            create_adult_user("Bob Adult", "+234800000002", bvn="98765432109", pin="4321", verified=True)
            uid2 = get_adult_by_phone("+234800000002")["id"]
            set_balance_user(uid2, 200.0)
        # seed kid
        create_kid_account(None, "+234700000001", "Kid One", "0000", "parent@example.com")
        add_money_kid("+234700000001", 150.0)
        st.success("Seeded demo data")
    st.markdown("### Users")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users")
    for r in cur.fetchall():
        st.write(dict(r))
    st.markdown("### Wallets")
    cur.execute("SELECT * FROM wallets")
    for r in cur.fetchall():
        st.write(dict(r))
    st.markdown("### Kids / Goals")
    cur.execute("SELECT * FROM kids")
    for r in cur.fetchall():
        st.write(dict(r))
    cur.execute("SELECT * FROM goals")
    for r in cur.fetchall():
        st.write(dict(r))
    st.markdown("### Withdrawals")
    cur.execute("SELECT * FROM withdrawals ORDER BY id DESC")
    for r in cur.fetchall():
        st.write(dict(r))

# -----------------------
# Alerts Log
# -----------------------
elif menu == "Alerts Log":
    st.header("Alerts log (SMS / Email)")
    cur = conn.cursor()
    cur.execute("SELECT * FROM alerts_log ORDER BY id DESC LIMIT 200")
    rows = cur.fetchall()
    if not rows:
        st.info("No alerts yet")
    else:
        for r in rows:
            st.write(f"[{r['time']}] {r['channel'].upper()} → {r['recipient']}: {r['message']}")

# -----------------------
# Provider Test
# -----------------------
elif menu == "Provider Test":
    st.header("Provider diagnostics")
    st.write("Provider:", PROVIDER)
    st.write("Base URL:", PROVIDER_BASE_URL)
    st.write("API key present:", bool(PROVIDER_API_KEY))
    kind = st.radio("Kind", ["nin", "bvn"])
    value = st.text_input("Value")
    if st.button("Run test"):
        res = verify_identity(kind, value.strip())
        st.json(res)

# Footer
st.markdown("---")
st.caption("NOT production-ready. Follow security steps: use KMS for secrets, enforce TLS, use proper KDF & auth, rate limit and obtain provider approvals.")
