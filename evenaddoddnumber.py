# banking_app.py
import streamlit as st
import sqlite3
from passlib.hash import bcrypt
from datetime import datetime

# ----------------------------
# Database Setup
# ----------------------------
def init_db():
    conn = sqlite3.connect("bank.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            nin TEXT,
            pin_hash TEXT,
            balance INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount INTEGER,
            timestamp TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

# ----------------------------
# Helpers
# ----------------------------
def hash_pin(pin: str) -> str:
    return bcrypt.hash(pin)

def check_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.verify(pin, pin_hash)

def get_user(phone):
    conn = sqlite3.connect("bank.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE phone=?", (phone,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(phone, nin, pin):
    conn = sqlite3.connect("bank.db")
    c = conn.cursor()
    pin_hash = hash_pin(pin)
    try:
        c.execute("INSERT INTO users (phone, nin, pin_hash) VALUES (?, ?, ?)", (phone, nin, pin_hash))
        conn.commit()
    except sqlite3.IntegrityError:
        st.error("Phone number already registered.")
    conn.close()

def update_balance(user_id, amount, tx_type):
    conn = sqlite3.connect("bank.db")
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, user_id))
    c.execute("INSERT INTO transactions (user_id, type, amount, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, tx_type, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_transactions(user_id):
    conn = sqlite3.connect("bank.db")
    c = conn.cursor()
    c.execute("SELECT type, amount, timestamp FROM transactions WHERE user_id=? ORDER BY id DESC", (user_id,))
    txs = c.fetchall()
    conn.close()
    return txs

# ----------------------------
# Streamlit App
# ----------------------------
st.set_page_config(page_title="Mini Banking App", page_icon="💰")

st.title("💳 Mini Banking App")

init_db()

menu = ["Signup", "Login"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Signup":
    st.subheader("Create an Account")
    phone = st.text_input("Phone Number")
    nin = st.text_input("NIN")
    pin = st.text_input("Set PIN", type="password")
    if st.button("Signup"):
        if phone and nin and pin:
            create_user(phone, nin, pin)
            st.success("Account created! You can now log in.")
        else:
            st.error("All fields are required.")

elif choice == "Login":
    st.subheader("Login to Your Account")
    phone = st.text_input("Phone Number")
    pin = st.text_input("PIN", type="password")

    if st.button("Login"):
        user = get_user(phone)
        if user and check_pin(pin, user[3]):  # user[3] = pin_hash
            st.success("Login successful!")
            st.session_state["user"] = user
        else:
            st.error("Invalid phone or PIN")

    if "user" in st.session_state:
        user = st.session_state["user"]
        st.write(f"**Welcome, {user[1]} 👋**")
        st.write(f"**Balance:** ₦{user[4] / 100:.2f}")

        col1, col2 = st.columns(2)

        with col1:
            deposit = st.number_input("Deposit Amount (₦)", min_value=0, step=100)
            if st.button("Deposit"):
                update_balance(user[0], int(deposit * 100), "Deposit")
                st.success(f"Deposited ₦{deposit}")
                st.session_state["user"] = get_user(user[1])  # refresh

        with col2:
            withdraw = st.number_input("Withdraw Amount (₦)", min_value=0, step=100)
            if st.button("Withdraw"):
                if withdraw * 100 <= user[4]:
                    update_balance(user[0], int(-withdraw * 100), "Withdraw")
                    st.success(f"Withdrew ₦{withdraw}")
                    st.session_state["user"] = get_user(user[1])  # refresh
                else:
                    st.error("Insufficient funds")

        st.subheader("📜 Transaction History")
        txs = get_transactions(user[0])
        for tx in txs:
            st.write(f"{tx[2]} | {tx[0]} | ₦{tx[1] / 100:.2f}")
