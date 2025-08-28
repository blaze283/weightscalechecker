# money_matters_kid_protected.py
# Streamlit app: Kid-safe banking prototype
# Features implemented (as requested):
# - Phone number used as account number (country code prefills; developer-changeable)
# - Parent creates kid accounts (kids cannot change account info)
# - Kids can view balance / QR and spend within limits
# - SMS OTP via Twilio if credentials added to st.secrets; otherwise OTP simulated
# - Accounts & transactions persist in SQLite
# - Parent Mode: approve external transfers, set allowances, daily limit, add pocket money
# - Basic checks: daily limit, allowance auto-credit, notifications

import streamlit as st
import sqlite3
import os
from datetime import datetime, timedelta, date
import hashlib
import secrets
import qrcode
from io import BytesIO
import base64
import json
import threading

# Try import Twilio -- optional
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except Exception:
    TWILIO_AVAILABLE = False

# -------------------- CONFIG --------------------
DEFAULT_COUNTRY_CODE = "+234"  # developer-changeable default country code (Nigeria example)
DB_PATH = "money_matters_kids.db"
OTP_EXPIRY_SECONDS = 300
ALLOWANCE_CHECK_HOURS = 24

# Twilio secret names expected in st.secrets (optional):
# st.secrets["twilio_account_sid"], st.secrets["twilio_auth_token"], st.secrets["twilio_from_number"]

# -------------------- DATABASE --------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # users: parents and kids
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        phone TEXT UNIQUE,
        country_code TEXT,
        name TEXT,
        role TEXT,
        parent_id INTEGER,
        pin_hash TEXT,
        balance REAL DEFAULT 0,
        daily_limit REAL DEFAULT 0,
        allowance_amount REAL DEFAULT 0,
        allowance_interval_days INTEGER DEFAULT 30,
        last_allowance_credit TEXT,
        last_spend_date TEXT,
        spent_today REAL DEFAULT 0
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        type TEXT,
        description TEXT,
        timestamp TEXT,
        approved INTEGER DEFAULT 1
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS otps (
        id INTEGER PRIMARY KEY,
        phone TEXT,
        code TEXT,
        expires_at TEXT
    )
    ''')
    conn.commit()
    conn.close()

init_db()

# -------------------- HELPERS --------------------

def hash_pin(pin: str, salt: str=None):
    if salt is None:
        salt = secrets.token_hex(8)
    dk = hashlib.pbkdf2_hmac('sha256', pin.encode(), salt.encode(), 100000)
    return salt + '$' + dk.hex()

def verify_pin(pin: str, stored: str):
    try:
        salt, hexhash = stored.split('$')
    except Exception:
        return False
    dk = hashlib.pbkdf2_hmac('sha256', pin.encode(), salt.encode(), 100000)
    return dk.hex() == hexhash

# get user by phone
def get_user_by_phone(phone):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    row = cur.fetchone(); conn.close()
    return row

# create user
def create_user(phone, country_code, name, role, pin, parent_id=None):
    conn = get_conn(); cur = conn.cursor()
    pin_hash = hash_pin(pin)
    cur.execute('''INSERT INTO users (phone, country_code, name, role, parent_id, pin_hash, balance)
                   VALUES (?,?,?,?,?,?,0)''', (phone, country_code, name, role, parent_id, pin_hash))
    conn.commit(); conn.close()

# add transaction
def add_transaction(user_id, amount, ttype, description, approved=1):
    conn = get_conn(); cur = conn.cursor()
    ts = datetime.utcnow().isoformat()
    cur.execute('''INSERT INTO transactions (user_id, amount, type, description, timestamp, approved)
                   VALUES (?,?,?,?,?,?)''', (user_id, amount, ttype, description, ts, int(approved)))
    # update balance if approved
    if approved:
        cur.execute('SELECT balance FROM users WHERE id=?',(user_id,))
        bal = cur.fetchone()[0] or 0
        bal += amount
        cur.execute('UPDATE users SET balance=? WHERE id=?',(bal,user_id))
    conn.commit(); conn.close()

# send or simulate OTP
def send_otp(phone, country_code, code):
    full = f"{country_code}{phone}"
    if TWILIO_AVAILABLE and all(k in st.secrets for k in ("twilio_account_sid","twilio_auth_token","twilio_from_number")):
        try:
            client = TwilioClient(st.secrets.twilio_account_sid, st.secrets.twilio_auth_token)
            message = client.messages.create(
                body=f"Your verification code: {code}",
                from_=st.secrets.twilio_from_number,
                to=full
            )
            return True, f"Sent via Twilio SID {message.sid}"
        except Exception as e:
            return False, f"Twilio error: {e}"
    # Otherwise simulate: store in db and print in Streamlit for dev
    return False, f"Simulated OTP: {code} (for {full})"

# store OTP
def store_otp(phone, code):
    conn = get_conn(); cur = conn.cursor()
    expires_at = (datetime.utcnow()+timedelta(seconds=OTP_EXPIRY_SECONDS)).isoformat()
    cur.execute('INSERT INTO otps (phone, code, expires_at) VALUES (?,?,?)', (phone, code, expires_at))
    conn.commit(); conn.close()

# verify OTP
def verify_otp(phone, code):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT * FROM otps WHERE phone=? ORDER BY id DESC LIMIT 1', (phone,))
    row = cur.fetchone()
    if not row:
        conn.close(); return False
    if row['code'] != code:
        conn.close(); return False
    if datetime.fromisoformat(row['expires_at']) < datetime.utcnow():
        conn.close(); return False
    conn.close(); return True

# QR image for account (shows phone)
def qr_for_phone(country_code, phone):
    data = json.dumps({"account": f"{country_code}{phone}"})
    img = qrcode.make(data)
    bio = BytesIO(); img.save(bio, format='PNG'); bio.seek(0)
    return bio

# check and credit allowances (runs on demand)
def process_allowances():
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE role="kid"')
    kids = cur.fetchall()
    for kid in kids:
        last = kid['last_allowance_credit']
        interval = kid['allowance_interval_days'] or 30
        amt = kid['allowance_amount'] or 0
        if amt <= 0: continue
        need = False
        if not last:
            need = True
        else:
            last_dt = datetime.fromisoformat(last)
            if datetime.utcnow() - last_dt >= timedelta(days=interval):
                need = True
        if need:
            # credit
            cur.execute('UPDATE users SET balance = balance + ?, last_allowance_credit = ? WHERE id = ?',(amt, datetime.utcnow().isoformat(), kid['id']))
            cur.execute('INSERT INTO transactions (user_id, amount, type, description, timestamp, approved) VALUES (?,?,?,?,?,1)', (kid['id'], amt, 'allowance', f'Allowance credit {amt}', datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

# reset daily spend counters if day changed
def reset_daily_spent_if_needed(user):
    today = date.today().isoformat()
    if user['last_spend_date'] != today:
        conn = get_conn(); cur = conn.cursor()
        cur.execute('UPDATE users SET spent_today = 0, last_spend_date = ? WHERE id = ?', (today, user['id']))
        conn.commit(); conn.close()

# -------------------- UI --------------------

st.set_page_config(page_title="Money Matters — Kids Banking (Prototype)", layout='wide')
st.title("Money Matters — Kids Banking (Prototype)")

# Simple sidebar: choose mode
mode = st.sidebar.selectbox("Choose mode", ["Home","Parent Login","Kid Login","Create Parent","Create Kid","Admin: Run Allowances"]) 

# Quick helper to format phone
def fmt_phone_input(label, default_country=DEFAULT_COUNTRY_CODE):
    cols = st.columns((1,2))
    cc = cols[0].text_input("Country code", value=default_country)
    phone = cols[1].text_input(label)
    return cc, phone

# HOME
if mode == "Home":
    st.write("This prototype uses the phone number as the account number. Parents create kid accounts and control allowances, limits, and approve transfers. To test: create a parent in 'Create Parent', then create a kid and use 'Kid Login'.")
    st.markdown("**Notes:** OTP will be sent via Twilio only if Twilio credentials exist in `st.secrets`. Otherwise OTP is simulated and shown.")

# CREATE PARENT
if mode == "Create Parent":
    st.header("Create Parent Account")
    country_code = st.text_input("Country code", value=DEFAULT_COUNTRY_CODE)
    phone = st.text_input("Phone (no country code)")
    name = st.text_input("Parent name")
    pin = st.text_input("Set 4-digit PIN", type='password')
    if st.button("Create Parent"):
        if not (phone and pin and name): st.error("Fill all fields"); st.stop()
        if get_user_by_phone(phone): st.error("Phone already registered"); st.stop()
        create_user(phone, country_code, name, 'parent', pin)
        st.success("Parent created. Use Parent Login.")

# CREATE KID
if mode == "Create Kid":
    st.header("Create Kid Account (Parent must exist)")
    parent_phone = st.text_input("Parent phone (no country code)")
    kid_name = st.text_input("Kid name")
    country_code = st.text_input("Country code", value=DEFAULT_COUNTRY_CODE)
    kid_phone = st.text_input("Kid phone (no country code)")
    pin = st.text_input("Kid PIN (4 digits)", type='password')
    initial_balance = st.number_input("Initial balance", min_value=0.0, value=0.0)
    allowance = st.number_input("Allowance amount (per interval)", min_value=0.0, value=0.0)
    allowance_interval = st.number_input("Allowance interval (days)", min_value=1, value=30)
    daily_limit = st.number_input("Daily spending limit", min_value=0.0, value=50.0)
    if st.button("Create Kid"):
        parent = get_user_by_phone(parent_phone)
        if not parent:
            st.error("Parent not found. Create parent first.")
        elif not (kid_phone and kid_name and pin):
            st.error("Provide kid name, phone, and pin")
        elif get_user_by_phone(kid_phone):
            st.error("Kid phone already registered")
        else:
            conn = get_conn(); cur = conn.cursor()
            pin_hash = hash_pin(pin)
            cur.execute('''INSERT INTO users (phone, country_code, name, role, parent_id, pin_hash, balance, daily_limit, allowance_amount, allowance_interval_days, last_allowance_credit, last_spend_date, spent_today)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', (kid_phone, country_code, kid_name, 'kid', parent['id'], pin_hash, initial_balance, daily_limit, allowance, allowance_interval, None, None, 0))
            conn.commit(); conn.close()
            st.success("Kid account created. Kid cannot change account info.")

# PARENT LOGIN
if mode == "Parent Login":
    st.header("Parent Login")
    country_code = st.text_input("Country code", value=DEFAULT_COUNTRY_CODE, key='pl_cc')
    phone = st.text_input("Phone (no country code)", key='pl_phone')
    pin = st.text_input("PIN", type='password', key='pl_pin')
    if st.button("Login as Parent"):
        user = get_user_by_phone(phone)
        if not user or user['role'] != 'parent': st.error("Parent not found")
        elif not verify_pin(pin, user['pin_hash']): st.error("Invalid PIN")
        else:
            st.session_state['user_id'] = user['id']
            st.session_state['role'] = 'parent'
            st.success(f"Welcome, {user['name']}")

    if st.session_state.get('role') == 'parent' and st.session_state.get('user_id'):
        # Parent dashboard
        st.subheader("Parent Dashboard")
        uid = st.session_state['user_id']
        conn = get_conn(); cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE id=?', (uid,))
        parent = cur.fetchone()
        st.write(f"Logged in as: {parent['name']} ({parent['country_code']}{parent['phone']})")
        # list children
        cur.execute('SELECT * FROM users WHERE parent_id=?',(uid,))
        kids = cur.fetchall()
        st.write("---")
        st.write("**Children:**")
        for k in kids:
            col1, col2, col3 = st.columns([2,1,1])
            col1.write(f"{k['name']} — {k['country_code']}{k['phone']}")
            col2.write(f"Balance: ₦{k['balance']:.2f}")
            if col3.button(f"Open {k['id']}", key=f"openkid{str(k['id'])}"):
                st.session_state['open_kid'] = k['id']
        st.write("---")
        # if open kid
        if st.session_state.get('open_kid'):
            kidid = st.session_state['open_kid']
            cur.execute('SELECT * FROM users WHERE id=?', (kidid,))
            kid = cur.fetchone()
            st.markdown(f"### Manage {kid['name']}")
            new_allow = st.number_input("Set allowance amount", value=kid['allowance_amount'] or 0.0, key='p_allow')
            new_interval = st.number_input("Allowance interval days", value=kid['allowance_interval_days'] or 30, key='p_interval')
            new_daily = st.number_input("Daily limit", value=kid['daily_limit'] or 0.0, key='p_daily')
            if st.button("Update settings for kid"):
                cur.execute('UPDATE users SET allowance_amount=?, allowance_interval_days=?, daily_limit=? WHERE id=?', (new_allow, int(new_interval), new_daily, kidid))
                conn.commit(); st.success("Updated")
            # add pocket money
            pocket = st.number_input("Add pocket money", value=0.0, key='pocket')
            if st.button("Credit pocket money"):
                if pocket>0:
                    add_transaction(kidid, pocket, 'credit', 'Pocket money (parent)')
                    st.success("Pocket money credited")
            # pending external transfers (transactions with approved=0)
            st.write("---")
            st.write("**Pending external transfers**")
            cur.execute('SELECT * FROM transactions WHERE approved=0')
            pend = cur.fetchall()
            for t in pend:
                st.write(f"ID {t['id']} — User {t['user_id']} — {t['amount']} — {t['description']}")
                if st.button(f"Approve {t['id']}", key=f"ap{t['id']}"):
                    # approve: apply amount
                    cur.execute('UPDATE transactions SET approved=1 WHERE id=?',(t['id'],))
                    # apply balance
                    cur.execute('SELECT balance FROM users WHERE id=?',(t['user_id'],))
                    bal = cur.fetchone()[0] or 0
                    bal += t['amount']
                    cur.execute('UPDATE users SET balance=? WHERE id=?',(bal, t['user_id']))
                    conn.commit(); st.success(f"Approved {t['id']}")
            conn.close()

# KID LOGIN
if mode == "Kid Login":
    st.header("Kid Login")
    country_code = st.text_input("Country code", value=DEFAULT_COUNTRY_CODE, key='kl_cc')
    phone = st.text_input("Kid phone (no country code)", key='kl_phone')
    pin = st.text_input("PIN", type='password', key='kl_pin')
    if st.button("Login as Kid"):
        user = get_user_by_phone(phone)
        if not user or user['role'] != 'kid': st.error("Kid not found")
        elif not verify_pin(pin, user['pin_hash']): st.error("Invalid PIN")
        else:
            st.session_state['user_id'] = user['id']
            st.session_state['role'] = 'kid'
            st.success(f"Welcome, {user['name']}")

    if st.session_state.get('role') == 'kid' and st.session_state.get('user_id'):
        uid = st.session_state['user_id']
        conn = get_conn(); cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE id=?',(uid,))
        kid = cur.fetchone()
        reset_daily_spent_if_needed(kid)
        st.write(f"Hello {kid['name']} — Balance: ₦{kid['balance']:.2f}")
        # QR view
        if st.button("Show QR for account"):
            bio = qr_for_phone(kid['country_code'], kid['phone'])
            st.image(bio)
        st.write("---")
        st.subheader("Spend / Transfer")
        to_phone = st.text_input("Recipient phone (no country code)")
        to_cc = st.text_input("Recipient country code", value=DEFAULT_COUNTRY_CODE)
        amount = st.number_input("Amount to send", min_value=0.0, value=0.0)
        desc = st.text_input("Description")
        if st.button("Request Transfer"):
            # checks: amount <= balance, daily limit
            if amount <= 0: st.error("Enter amount"); st.stop()
            if amount > kid['balance']:
                st.error("Insufficient balance"); st.stop()
            # daily limit
            reset_daily_spent_if_needed(kid)
            conn = get_conn(); cur = conn.cursor()
            cur.execute('SELECT spent_today, daily_limit FROM users WHERE id=?',(uid,))
            row = cur.fetchone(); spent_today = row['spent_today'] or 0; daily_limit = row['daily_limit'] or 0
            if daily_limit>0 and (spent_today + amount) > daily_limit:
                st.error(f"Exceeds daily limit. Spent today {spent_today}, limit {daily_limit}")
                conn.close(); st.stop()
            # find recipient
            recipient = get_user_by_phone(to_phone)
            if recipient:
                # internal transfer: immediate if parent-approved? Children cannot approve external transfers; we will enqueue as approved=1 for internal transfers but parents can review
                add_transaction(uid, -amount, 'debit', f'Transfer to {to_cc}{to_phone}')
                add_transaction(recipient['id'], amount, 'credit', f'Received from {kid["country_code"]}{kid["phone"]}')
                # update spent_today
                cur.execute('UPDATE users SET spent_today = spent_today + ? WHERE id=?', (amount, uid))
                conn.commit(); conn.close(); st.success("Transfer completed to internal user")
            else:
                # external transfer: create a pending transaction for approval by parent
                add_transaction(uid, -amount, 'debit', f'External transfer to {to_cc}{to_phone}', approved=0)
                conn.close(); st.info("External transfer requested — awaiting parent approval")

# ADMIN: run automatic allowance process
if mode == "Admin: Run Allowances":
    st.header("Admin: Process allowances now")
    if st.button("Run allowance job now"):
        process_allowances()
        st.success("Allowances processed")

# Small utilities: view transactions for logged-in users
if st.session_state.get('user_id'):
    uid = st.session_state['user_id']
    conn = get_conn(); cur = conn.cursor()
    cur.execute('SELECT * FROM transactions WHERE user_id=? ORDER BY timestamp DESC LIMIT 50',(uid,))
    txs = cur.fetchall()
    if txs:
        st.write('---')
        st.write('Recent transactions:')
        for t in txs:
            st.write(f"{t['timestamp']}: {t['type']} {t['amount']} — {t['description']} — Approved: {bool(t['approved'])}")
    conn.close()

# Send OTP utility UI (for testing flows)
st.sidebar.write('---')
st.sidebar.subheader('Dev / OTP')
otp_phone = st.sidebar.text_input('Test phone (no cc)', key='otp_phone')
otp_cc = st.sidebar.text_input('Test country code', value=DEFAULT_COUNTRY_CODE, key='otp_cc')
if st.sidebar.button('Send test OTP'):
    code = str(secrets.randbelow(10**6)).zfill(6)
    ok, msg = send_otp(otp_phone, otp_cc, code)
    store_otp(otp_phone, code)
    if ok:
        st.sidebar.success(msg)
    else:
        st.sidebar.info(msg)

# Helpful run instructions
st.sidebar.write('---')
st.sidebar.markdown('**Run:** `streamlit run money_matters_kid_protected.py`')
st.sidebar.markdown('**Twilio** (optional): add `twilio_account_sid`, `twilio_auth_token`, `twilio_from_number` to `st.secrets` to enable SMS sending.')

# End of file
