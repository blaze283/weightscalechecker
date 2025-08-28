import streamlit as st
import sqlite3
import hashlib
import os
from datetime import datetime

DB_PATH = "nedbank_kids.db"

# ----------------- Helpers (DB + Security) -----------------

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parent (
        id INTEGER PRIMARY KEY,
        pin_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS kids (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        allowance REAL DEFAULT 0,
        balance REAL DEFAULT 0,
        lock_spending INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sms_log (
        id INTEGER PRIMARY KEY,
        recipient TEXT,
        message TEXT,
        time TEXT
    )
    """)
    conn.commit()
    return conn


def hash_pin(pin: str) -> str:
    # simple salted sha256 — OK for demo, use a stronger KDF in production
    salt = "nedbank-demo-salt"
    return hashlib.sha256((salt + pin).encode()).hexdigest()


def parent_exists(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM parent")
    return cur.fetchone()[0] > 0


def create_parent(conn, pin):
    cur = conn.cursor()
    cur.execute("INSERT INTO parent (pin_hash, created_at) VALUES (?,?)", (hash_pin(pin), datetime.utcnow().isoformat()))
    conn.commit()


def verify_parent_pin(conn, pin) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT pin_hash FROM parent LIMIT 1")
    row = cur.fetchone()
    if not row:
        return False
    return row[0] == hash_pin(pin)


def add_kid(conn, name, phone, allowance=0.0, lock_spending=False):
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO kids (name, phone, allowance, balance, lock_spending, created_at) VALUES (?,?,?,?,?,?)",
            (name, phone, float(allowance), float(allowance), int(lock_spending), datetime.utcnow().isoformat()),
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, str(e)


def update_kid(conn, kid_id, **patch):
    cur = conn.cursor()
    allowed = ["name", "phone", "allowance", "balance", "lock_spending"]
    sets = []
    vals = []
    for k, v in patch.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    vals.append(kid_id)
    cur.execute(f"UPDATE kids SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    return True


def get_kids(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM kids ORDER BY id DESC")
    return cur.fetchall()


def get_kid_by_phone(conn, phone):
    cur = conn.cursor()
    cur.execute("SELECT * FROM kids WHERE phone = ?", (phone,))
    return cur.fetchone()


def get_kid(conn, kid_id):
    cur = conn.cursor()
    cur.execute("SELECT * FROM kids WHERE id = ?", (kid_id,))
    return cur.fetchone()


def log_sms(conn, recipient, message):
    cur = conn.cursor()
    cur.execute("INSERT INTO sms_log (recipient, message, time) VALUES (?,?,?)", (recipient, message, datetime.utcnow().isoformat()))
    conn.commit()


def get_sms(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM sms_log ORDER BY id DESC")
    return cur.fetchall()


# ----------------- Streamlit UI -----------------

st.set_page_config(page_title="Nedbank Kids — Demo (Streamlit)", layout="centered")

if not os.path.exists(DB_PATH):
    conn = init_db()
else:
    conn = get_db()

st.title("Nedbank Kids — Demo (Streamlit)")
st.caption("Demo only — not for real banking. Do not use with real funds or personal data.")

menu = st.sidebar.selectbox("Navigation", ["Home", "Parent: Setup / Portal", "Kid: Login / View", "SMS Log"])

# Home
if menu == "Home":
    st.header("What this demo does")
    st.markdown(
        """
        - Parent: create a PIN, add child accounts (phone number used as account ID), set allowance and lock spending.
        - Kid: simple read-only view; kids can request money (sends simulated SMS to parent).
        - All data stored locally in a SQLite database `nedbank_kids.db` in the app folder.

        **This is a prototype**. For production you'd add secure server-side authentication, encryption, proper PIN hashing (e.g. Argon2), bank API integrations, and legal agreements.
        """
    )
    st.write("Database file:", DB_PATH)

# Parent area (setup + portal)
if menu == "Parent: Setup / Portal":
    st.header("Parent Portal")
    if not parent_exists(conn):
        st.subheader("Create Parent PIN")
        pin = st.text_input("Choose a 4+ digit PIN", type="password")
        pin2 = st.text_input("Confirm PIN", type="password")
        if st.button("Create PIN"):
            if not pin or len(pin) < 4:
                st.error("PIN must be at least 4 digits")
            elif pin != pin2:
                st.error("PINs do not match")
            else:
                create_parent(conn, pin)
                st.success("Parent PIN created — return to Parent Portal and enter your PIN to manage kids")
    else:
        st.subheader("Enter your Parent PIN")
        pin = st.text_input("Parent PIN", type="password")
        if st.button("Unlock Portal"):
            if verify_parent_pin(conn, pin):
                st.session_state.parent_unlocked = True
                st.success("Portal unlocked")
            else:
                st.session_state.parent_unlocked = False
                st.error("Wrong PIN")

        if st.session_state.get("parent_unlocked"):
            st.subheader("Manage children")
            cols = st.columns(2)
            with cols[0]:
                st.markdown("### Add child account")
                name = st.text_input("Child name", key="add_name")
                country_code = st.selectbox("Country code", ["+27 (South Africa)", "+234 (Nigeria)", "+1 (USA/Canada)", "+44 (UK)"], index=0)
                phone_suffix = st.text_input("Phone (without country code)", key="add_phone")
                allowance = st.number_input("Initial allowance", min_value=0.0, value=0.0, step=1.0)
                lock_spend = st.checkbox("Lock spending for this child", value=False)
                if st.button("Create child"):
                    full_phone = country_code.split()[0] + phone_suffix.strip()
                    ok, err = add_kid(conn, name.strip(), full_phone, allowance, lock_spend)
                    if ok:
                        st.success(f"Child {name} created with phone {full_phone}")
                    else:
                        st.error(f"Failed to create child: {err}")

            with cols[1]:
                st.markdown("### Existing children")
                kids = get_kids(conn)
                if not kids:
                    st.info("No children created yet")
                for row in kids:
                    st.write(f"**{row['name']}** — {row['phone']} — Balance: R{row['balance']} — Allowance: R{row['allowance']} {'(Locked)' if row['lock_spending'] else ''}")
                    kcols = st.columns([1,1,1,2])
                    if kcols[0].button("Edit", key=f"edit_{row['id']}"):
                        st.session_state.edit_kid = row['id']
                    if kcols[1].button("Top-up R50", key=f"top_{row['id']}"):
                        new_bal = row['balance'] + 50
                        update_kid(conn, row['id'], balance=new_bal)
                        log_sms(conn, "Parent", f"Credited R50 to {row['name']}")
                        st.experimental_rerun()
                    if kcols[2].button("Delete", key=f"del_{row['id']}"):
                        cur = conn.cursor()
                        cur.execute("DELETE FROM kids WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.success("Deleted")
                        st.experimental_rerun()

            # show edit form if requested
            if st.session_state.get("edit_kid"):
                kid = get_kid(conn, st.session_state.edit_kid)
                if kid:
                    st.markdown("---")
                    st.subheader(f"Editing {kid['name']}")
                    new_name = st.text_input("Name", value=kid['name'], key="edit_name")
                    new_phone = st.text_input("Phone", value=kid['phone'], key="edit_phone")
                    new_allow = st.number_input("Allowance", min_value=0.0, value=float(kid['allowance']), key="edit_allow")
                    new_lock = st.checkbox("Lock spending", value=bool(kid['lock_spending']), key="edit_lock")
                    if st.button("Save changes", key="save_edit"):
                        update_kid(conn, kid['id'], name=new_name, phone=new_phone, allowance=new_allow, balance=new_allow, lock_spending=int(new_lock))
                        st.success("Saved")
                        del st.session_state["edit_kid"]
                        st.experimental_rerun()

# Kid area
if menu == "Kid: Login / View":
    st.header("Kid — Read-only Wallet (Demo)")
    st.write("Enter the child phone (with country code) to access the kid view")
    phone = st.text_input("Phone (e.g. +27812345678)")
    if st.button("Enter as kid"):
        kid = get_kid_by_phone(conn, phone.strip())
        if not kid:
            st.error("No child found with that phone (create one in Parent Portal first)")
        else:
            st.session_state.kid_id = kid['id']
            st.experimental_rerun()

    if st.session_state.get("kid_id"):
        kid = get_kid(conn, st.session_state.kid_id)
        if kid:
            st.subheader(f"{kid['name']}'s Wallet")
            st.write(f"Phone: {kid['phone']}")
            st.write(f"Balance: R{kid['balance']}")
            if kid['lock_spending']:
                st.error("Spending locked by parent")
            spend = st.button("Spend (demo)", disabled=bool(kid['lock_spending']))
            if spend:
                st.info("This is a demo — no real spending implemented")

            st.markdown("---")
            st.subheader("Request money from parent")
            req_amount = st.number_input("Amount", min_value=0.0, value=0.0)
            req_msg = st.text_input("Message (optional)")
            if st.button("Send request"):
                recipient = "Parent"
                message = f"Request from {kid['name']} ({kid['phone']}): R{req_amount} — {req_msg}"
                log_sms(conn, recipient, message)
                st.success("Request sent to parent (simulated SMS)")

            if st.button("Logout kid"):
                del st.session_state['kid_id']
                st.experimental_rerun()

# SMS Log
if menu == "SMS Log":
    st.header("Simulated SMS / Notifications")
    sms = get_sms(conn)
    if not sms:
        st.info("No messages yet")
    for s in sms:
        st.write(f"[{s['time']}] To: {s['recipient']} — {s['message']}")


# Footer
st.markdown("---")
st.caption("Demo app created for prototyping learning purposes. For production banking apps use secure, audited infrastructure and coordinate with the bank.")
