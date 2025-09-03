# mini_bank.py
import streamlit as st
import sqlite3
from passlib.hash import bcrypt
from datetime import datetime, date
import uuid
import os

DB_FILE = "bank.db"
DAILY_GAME_CAP = 5000  # in kobo (₦50.00) — set to what you want

# ----------------------------
# Database helpers
# ----------------------------
def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            phone TEXT UNIQUE,
            nin TEXT,
            pin_hash TEXT,
            balance INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT,
            amount INTEGER,
            timestamp TEXT,
            note TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ----------------------------
# Helpers: PIN, users, wallet, txs
# ----------------------------
def hash_pin(pin: str) -> str:
    return bcrypt.hash(pin)

def check_pin(pin: str, pin_hash: str) -> bool:
    if not pin_hash:
        return False
    try:
        return bcrypt.verify(pin, pin_hash)
    except Exception:
        return False

def create_user(phone: str, nin: str, pin: str):
    conn = get_conn()
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    pin_hash = hash_pin(pin)
    try:
        c.execute("INSERT INTO users (id, phone, nin, pin_hash, balance) VALUES (?,?,?,?,?)",
                  (user_id, phone, nin, pin_hash, 0))
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def get_user_by_phone(phone: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    u = c.fetchone()
    conn.close()
    return u

def get_user_by_id(user_id: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    u = c.fetchone()
    conn.close()
    return u

def update_balance(user_id: str, delta_kobo: int, tx_type: str, note: str = ""):
    conn = get_conn()
    c = conn.cursor()
    tx_id = str(uuid.uuid4())
    ts = datetime.utcnow().isoformat()
    # update balance
    c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (delta_kobo, user_id))
    # insert transaction
    c.execute("INSERT INTO transactions (id, user_id, type, amount, timestamp, note) VALUES (?,?,?,?,?,?)",
              (tx_id, user_id, tx_type, delta_kobo, ts, note))
    conn.commit()
    conn.close()

def get_transactions(user_id: str, limit: int = 100):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT type, amount, timestamp, note FROM transactions WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
              (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def get_today_game_rewards(user_id: str):
    """Sum of 'game_reward' amounts awarded today (kobo)."""
    conn = get_conn()
    c = conn.cursor()
    today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
    c.execute("SELECT COALESCE(SUM(amount), 0) as s FROM transactions WHERE user_id = ? AND type = 'game_reward' AND timestamp >= ?",
              (user_id, today_start))
    r = c.fetchone()
    conn.close()
    return r["s"] if r else 0

# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="Mini Bank", page_icon="💰", layout="centered")
st.title("💜 Mini Banking App — MVP")

# initialize session
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None

menu = st.sidebar.selectbox("Menu", ["Signup", "Login", "Dashboard", "Logout"])

# ----------------------------
# Signup
# ----------------------------
if menu == "Signup":
    st.header("Create account")
    phone = st.text_input("Phone (e.g. +2348012345678)")
    nin = st.text_input("NIN (optional)")
    pin = st.text_input("Set 4-digit PIN", type="password")
    pin_confirm = st.text_input("Confirm PIN", type="password")
    if st.button("Create account"):
        if not phone or not pin:
            st.error("Phone and PIN are required")
        elif pin != pin_confirm:
            st.error("PINs do not match")
        else:
            uid = create_user(phone.strip(), nin.strip(), pin.strip())
            if uid:
                st.success("Account created. Please login from the Login menu.")
            else:
                st.error("Phone already registered. Try logging in.")

# ----------------------------
# Login
# ----------------------------
elif menu == "Login":
    st.header("Login")
    phone = st.text_input("Phone")
    pin = st.text_input("PIN", type="password")
    if st.button("Login"):
        user = get_user_by_phone(phone.strip())
        if not user:
            st.error("User not found. Please sign up.")
        else:
            if check_pin(pin.strip(), user["pin_hash"]):
                st.session_state["user_id"] = user["id"]
                st.success("Logged in successfully.")
            else:
                st.error("Incorrect PIN.")

# ----------------------------
# Dashboard (requires login)
# ----------------------------
elif menu == "Dashboard":
    if not st.session_state.get("user_id"):
        st.info("Please login first.")
    else:
        uid = st.session_state["user_id"]
        user = get_user_by_id(uid)
        st.subheader(f"Welcome — {user['phone']}")
        st.write(f"**Balance:** ₦{user['balance'] / 100:.2f}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Deposit (simulate)")
            deposit = st.number_input("Amount (NGN)", min_value=0.0, format="%.2f", key="deposit")
            if st.button("Deposit"):
                if deposit <= 0:
                    st.error("Enter a positive amount")
                else:
                    amt_kobo = int(deposit * 100)
                    update_balance(uid, amt_kobo, "deposit", note="User deposit (simulated)")
                    st.success(f"Deposited ₦{deposit:.2f}")
                    st.experimental_rerun()

        with col2:
            st.markdown("### Withdraw (simulate)")
            withdraw = st.number_input("Amount (NGN)", min_value=0.0, format="%.2f", key="withdraw")
            if st.button("Withdraw"):
                amt_kobo = int(withdraw * 100)
                if amt_kobo <= 0:
                    st.error("Enter a positive amount")
                elif amt_kobo > user["balance"]:
                    st.error("Insufficient funds")
                else:
                    update_balance(uid, -amt_kobo, "withdraw", note="User withdrawal (simulated)")
                    st.success(f"Withdrew ₦{withdraw:.2f}")
                    st.experimental_rerun()

        st.markdown("---")
        st.markdown("### Play: Spin & Win")
        st.write("Spin once to win a small wallet credit. Daily cap applies.")
        if st.button("Spin & Win"):
            # compute today's rewards and remaining cap
            today_awarded = get_today_game_rewards(uid)
            remaining = DAILY_GAME_CAP - today_awarded
            if remaining <= 0:
                st.error("Daily game reward cap reached. Try again tomorrow.")
            else:
                # reward random between ₦10 - ₦200 (1000 - 20000 kobo), but not exceeding remaining
                import random
                min_kobo = 1000
                max_kobo = 20000
                reward = random.randint(min_kobo, max_kobo)
                if reward > remaining:
                    reward = remaining
                update_balance(uid, reward, "game_reward", note="Spin & Win prize")
                st.success(f"You won ₦{reward/100:.2f}!")
                st.experimental_rerun()

        st.markdown("---")
        st.subheader("Transaction History (recent)")
        txs = get_transactions(uid, limit=50)
        if not txs:
            st.write("No transactions yet.")
        else:
            for t in txs:
                typ = t["type"]
                amt = t["amount"]
                ts = t["timestamp"]
                note = t["note"] or ""
                sign = "+" if amt >= 0 else "-"
                st.write(f"{ts} • {typ} • {sign} ₦{abs(amt)/100:.2f} • {note}")

# ----------------------------
# Logout
# ----------------------------
elif menu == "Logout":
    if st.session_state.get("user_id"):
        st.session_state["user_id"] = None
        st.success("Logged out.")
    else:
        st.info("You are not logged in.")

