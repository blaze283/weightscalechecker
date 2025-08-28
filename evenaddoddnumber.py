import streamlit as st
import sqlite3

# ------------------- DATABASE -------------------
conn = sqlite3.connect("kids_savings.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS kids (
    phone TEXT PRIMARY KEY,
    name TEXT,
    balance REAL DEFAULT 0
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    goal_name TEXT,
    target REAL,
    saved REAL DEFAULT 0
)
""")
conn.commit()

# ------------------- FUNCTIONS -------------------
def create_kid(phone, name):
    cur.execute("INSERT OR IGNORE INTO kids (phone, name, balance) VALUES (?, ?, 0)", (phone, name))
    conn.commit()

def get_balance(phone):
    cur.execute("SELECT balance FROM kids WHERE phone=?", (phone,))
    row = cur.fetchone()
    return row[0] if row else 0

def add_money(phone, amount):
    cur.execute("UPDATE kids SET balance = balance + ? WHERE phone=?", (amount, phone))
    conn.commit()

def create_goal(phone, goal_name, target):
    cur.execute("INSERT INTO goals (phone, goal_name, target, saved) VALUES (?, ?, ?, 0)",
                (phone, goal_name, target))
    conn.commit()

def get_goals(phone):
    cur.execute("SELECT id, goal_name, target, saved FROM goals WHERE phone=?", (phone,))
    return cur.fetchall()

def save_to_goal(goal_id, phone, amount):
    bal = get_balance(phone)
    if bal >= amount:
        # reduce balance
        cur.execute("UPDATE kids SET balance = balance - ? WHERE phone=?", (amount, phone))
        # add to goal
        cur.execute("UPDATE goals SET saved = saved + ? WHERE id=?", (amount, goal_id))
        conn.commit()
        return True
    return False

# ------------------- APP UI -------------------
st.set_page_config(page_title="Kids Savings App", page_icon="💰", layout="centered")

st.title("💰 Kids Savings App")

menu = ["Register", "Login"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Register":
    st.subheader("👶 Register")
    phone = st.text_input("Parent Phone Number (used as account)")
    name = st.text_input("Kid's Name")
    if st.button("Register"):
        if phone and name:
            create_kid(phone, name)
            st.success(f"Account created for {name} with phone {phone}!")
        else:
            st.error("Please enter all fields")

elif choice == "Login":
    st.subheader("🔑 Login")
    phone = st.text_input("Enter phone number")
    if st.button("Login"):
        cur.execute("SELECT name FROM kids WHERE phone=?", (phone,))
        row = cur.fetchone()
        if row:
            st.session_state["phone"] = phone
            st.session_state["name"] = row[0]
            st.success(f"Welcome back {row[0]}!")
        else:
            st.error("Account not found. Please register.")

# ------------------- Dashboard -------------------
if "phone" in st.session_state:
    phone = st.session_state["phone"]
    name = st.session_state["name"]

    st.header(f"Hello, {name} 👋")
    st.write(f"📱 Phone: {phone}")

    st.metric("Wallet Balance", f"₦{get_balance(phone):,.2f}")

    # Top up
    st.subheader("➕ Add Money")
    amount = st.number_input("Enter amount to add", min_value=0.0, step=100.0)
    if st.button("Add to Wallet"):
        add_money(phone, amount)
        st.success(f"₦{amount:,.2f} added!")

    # Goals
    st.subheader("🎯 Savings Goals")
    goals = get_goals(phone)
    for g in goals:
        gid, gname, target, saved = g
        st.progress(min(saved / target, 1.0))
        st.write(f"{gname}: ₦{saved:,.2f} / ₦{target:,.2f}")
        amt = st.number_input(f"Save into {gname}", min_value=0.0, step=100.0, key=f"goal_{gid}")
        if st.button(f"Save {amt} → {gname}", key=f"btn_{gid}"):
            if save_to_goal(gid, phone, amt):
                st.success(f"Saved ₦{amt:,.2f} into {gname}")
            else:
                st.error("Not enough balance!")

    st.subheader("➕ Create New Goal")
    gname = st.text_input("Goal name")
    target = st.number_input("Target amount", min_value=100.0, step=100.0)
    if st.button("Create Goal"):
        create_goal(phone, gname, target)
        st.success(f"Goal '{gname}' created with target ₦{target:,.2f}")
