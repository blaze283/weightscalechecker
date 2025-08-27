import streamlit as st
import datetime as dt
from forex_python.converter import CurrencyRates
import qrcode
from io import BytesIO
import requests

# ====================== CONFIG ======================
st.set_page_config(page_title="Money Matters", page_icon="💰", layout="centered")
LOCAL_CURRENCY = "NGN"
PARENT_PASSWORD = "parent123"   # 🔑 change this!

# ====================== SERVICES ======================
def get_currency_service():
    try:
        return CurrencyRates()
    except Exception:
        return None

c = get_currency_service()

def convert_to_local(amount: float, from_code: str) -> float:
    if from_code.upper() == LOCAL_CURRENCY:
        return float(amount)
    if c is None:
        # Fallback demo rate when offline/no service
        demo_rates = {"USD": 1600.0, "EUR": 1700.0, "GBP": 2000.0}
        rate = demo_rates.get(from_code.upper(), 1500.0)
        return float(amount) * rate
    return float(c.convert(from_code.upper(), LOCAL_CURRENCY, amount))

def make_qr(data: str) -> bytes:
    img = qrcode.make(data)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def flutterwave_available():
    return "flutterwave" in st.secrets and "secret_key" in st.secrets["flutterwave"]

def kora_available():
    return "kora" in st.secrets and "api_key" in st.secrets["kora"]

def send_flutterwave_transfer(amount, acct_no, bank_code, reference):
    if not flutterwave_available():
        return {"status": "success", "mode": "test", "message": "Simulated Flutterwave transfer"}
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
        return {"status": "success", "mode": "test", "message": "Simulated Palmpay transfer (Kora)"}
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

# ====================== STATE ======================
if "kids" not in st.session_state:
    st.session_state.kids = {}  # name -> data
if "current_kid" not in st.session_state:
    st.session_state.current_kid = None
if "parent_mode" not in st.session_state:
    st.session_state.parent_mode = False
if "app_date" not in st.session_state:
    st.session_state.app_date = dt.date.today()  # track day to reset spent_today
if "last_allowance_check" not in st.session_state:
    st.session_state.last_allowance_check = dt.date.today()

def init_kid(name: str):
    st.session_state.kids[name] = {
        "balance": 0.0,
        "transactions": [],
        "goal_amount": 0.0,
        "goal_name": "",
        "stars": 0,
        "badges": set(),
        "daily_limit": 500.0,
        "spent_today": 0.0,
        "last_spending_reset": dt.date.today().isoformat(),
        "allowance": {"amount": 0.0, "frequency": None, "last_paid": None},
        "notifications": [],  # list of strings
    }

def get_kid():
    return st.session_state.kids[st.session_state.current_kid]

def add_tx(kid, tx_type, amount, currency, converted):
    kid["transactions"].append({
        "date": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": tx_type,
        "amount": float(amount),
        "currency": currency,
        "converted": float(converted),
    })

def notify(kid, text: str):
    kid["notifications"].append(f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M')} — {text}")

# ====================== DAILY RESET & ALLOWANCES ======================
def reset_spending_if_new_day():
    today = dt.date.today()
    if st.session_state.app_date != today:
        for kd in st.session_state.kids.values():
            kd["spent_today"] = 0.0
            kd["last_spending_reset"] = today.isoformat()
        st.session_state.app_date = today

def apply_allowances_once_per_day():
    today = dt.date.today()
    if st.session_state.last_allowance_check == today:
        return
    for kid_name, kd in st.session_state.kids.items():
        alw = kd["allowance"]
        if not alw or alw["amount"] <= 0 or not alw["frequency"]:
            continue
        last_paid = alw["last_paid"]
        freq = alw["frequency"]
        pay = False
        if freq == "Daily":
            pay = (last_paid != today)
        elif freq == "Weekly":
            pay = (last_paid is None) or ((today - last_paid).days >= 7)
        elif freq == "Monthly":
            pay = (last_paid is None) or (today.month != last_paid.month or today.year != last_paid.year)
        if pay:
            amt = float(alw["amount"])
            kd["balance"] += amt
            add_tx(kd, f"Allowance ({freq})", amt, LOCAL_CURRENCY, amt)
            kd["allowance"]["last_paid"] = today
            notify(kd, f"Allowance credited: +{amt:.2f} {LOCAL_CURRENCY}")
    st.session_state.last_allowance_check = today

reset_spending_if_new_day()
apply_allowances_once_per_day()

# ====================== HEADER ======================
st.title("💳 Money Matters")
st.caption("Fun, safe banking for kids — with goals, rewards, QR, allowances & secure transfers.")
st.info(f"All balances are kept in **{LOCAL_CURRENCY}**.")

# ====================== SIDEBAR: PARENT MODE ======================
with st.sidebar:
    st.subheader("👨‍👩‍👧 Parent Mode")
    if not st.session_state.parent_mode:
        pw = st.text_input("Parent Password", type="password")
        if st.button("Login"):
            if pw == PARENT_PASSWORD:
                st.session_state.parent_mode = True
                st.success("Parent Mode Activated")
            else:
                st.error("Wrong password")
    else:
        st.success("Parent Mode Active")
        if st.button("Logout"):
            st.session_state.parent_mode = False

        # Create kid accounts
        st.markdown("---")
        new_kid = st.text_input("Add Kid Account (name)")
        if st.button("Create Kid") and new_kid:
            if new_kid in st.session_state.kids:
                st.warning("Kid already exists.")
            else:
                init_kid(new_kid)
                st.success(f"Created account for {new_kid}")

        # Parent Dashboard
        if st.session_state.kids:
            st.markdown("---")
            st.subheader("📊 Parent Dashboard")
            for nm, kd in st.session_state.kids.items():
                st.metric(label=f"{nm}'s Balance", value=f"{kd['balance']:.2f} {LOCAL_CURRENCY}")
            # Controls
            st.markdown("---")
            st.subheader("⚙️ Controls")
            kid_choice_parent = st.selectbox("Choose Kid", list(st.session_state.kids.keys()), key="parent_pick")
            kd = st.session_state.kids[kid_choice_parent]
            alw_amt = st.number_input("Allowance Amount", min_value=0.0, step=100.0, value=float(kd["allowance"]["amount"]))
            alw_freq = st.selectbox("Allowance Frequency", ["None", "Daily", "Weekly", "Monthly"],
                                    index=["None","Daily","Weekly","Monthly"].index(kd["allowance"]["frequency"] or "None"))
            dlimit = st.number_input("Daily Spending Limit", min_value=0.0, step=50.0, value=float(kd["daily_limit"]))
            if st.button("Save Settings"):
                kd["allowance"]["amount"] = alw_amt
                kd["allowance"]["frequency"] = None if alw_freq == "None" else alw_freq
                kd["daily_limit"] = dlimit
                st.success("Settings updated")

# ====================== SELECT KID ======================
if not st.session_state.kids:
    st.warning("No kid accounts yet. Parent must create one in Parent Mode.")
    st.stop()

kid_choice = st.selectbox("Select Kid Account", list(st.session_state.kids.keys()), key="kid_pick")
st.session_state.current_kid = kid_choice
kid = get_kid()

# ====================== NOTIFICATIONS ======================
with st.expander("🔔 Notifications", expanded=False):
    if kid["notifications"]:
        for n in reversed(kid["notifications"]):
            st.info(n)
        if st.button("Mark all as read"):
            kid["notifications"].clear()
    else:
        st.write("No notifications yet.")

# ====================== DEPOSIT / WITHDRAW ======================
st.subheader("💵 Deposit & Withdraw")
col1, col2 = st.columns(2)

with col1:
    dep_amt = st.number_input("Deposit amount", min_value=1.0, step=1.0, key="dep_amt")
    dep_ccy = st.text_input("Deposit currency (e.g., USD, EUR, GBP)", "USD", key="dep_ccy")
    if st.button("Deposit"):
        try:
            converted = convert_to_local(dep_amt, dep_ccy)
            kid["balance"] += converted
            add_tx(kid, "Deposit", dep_amt, dep_ccy.upper(), converted)
            # Rewards
            if converted < 1000: kid["stars"] += 1
            elif converted < 5000: kid["stars"] += 3
            else: kid["stars"] += 5
            if len([t for t in kid["transactions"] if t["type"] == "Deposit"]) == 1:
                kid["badges"].add("🎖️ Starter Saver")
            if kid["balance"] >= 10000:
                kid["badges"].add("🏆 Big Saver")
            st.success(f"Deposited {dep_amt} {dep_ccy.upper()} = {converted:.2f} {LOCAL_CURRENCY}")
        except Exception as e:
            st.error(f"Deposit failed: {e}")

with col2:
    w_amt = st.number_input("Withdraw (in NGN)", min_value=1.0, step=1.0, key="w_amt")
    if st.button("Withdraw"):
        if w_amt > kid["balance"]:
            st.error("Not enough balance")
        else:
            # Daily limit check (spending)
            if kid["spent_today"] + w_amt > kid["daily_limit"] and kid["daily_limit"] > 0:
                st.error("Daily spending limit reached")
            else:
                kid["balance"] -= w_amt
                kid["spent_today"] += w_amt
                add_tx(kid, "Withdrawal", w_amt, LOCAL_CURRENCY, w_amt)
                st.success(f"Withdrew {w_amt:.2f} {LOCAL_CURRENCY}")

# 80% daily limit warning
if kid["daily_limit"] > 0:
    used_ratio = (kid["spent_today"] / kid["daily_limit"]) if kid["daily_limit"] else 0
    if used_ratio >= 0.8 and used_ratio < 1.0:
        st.warning(f"⚠️ You've used {used_ratio*100:.0f}% of your daily limit.")
        notify(kid, f"Daily limit nearing: {used_ratio*100:.0f}% used today.")

# ====================== QR PAYMENTS (P2P) ======================
st.subheader("📲 P2P QR Payments")
tab1, tab2 = st.tabs(["Generate QR to Receive", "Scan QR to Send"])

with tab1:
    req_amt = st.number_input("Request amount (NGN)", min_value=1.0, step=1.0, key="req_amt")
    if st.button("Generate Payment QR"):
        qr_data = f"PAYTO:{kid_choice}:{req_amt}"
        img = make_qr(qr_data)
        st.image(img, caption=f"Scan to pay {kid_choice} {req_amt} {LOCAL_CURRENCY}", width=220)
        st.download_button("Download QR", img, file_name=f"{kid_choice}_request_qr.png", mime="image/png")

with tab2:
    qr_text = st.text_input("Paste QR text here (e.g., PAYTO:Sam:500)")
    if st.button("Send via QR"):
        if not qr_text.startswith("PAYTO:"):
            st.error("Invalid QR text")
        else:
            try:
                _, receiver, amt = qr_text.split(":")
                amt = float(amt)
                if receiver not in st.session_state.kids:
                    st.error("Receiver not found")
                elif amt > kid["balance"]:
                    st.error("Not enough balance")
                elif kid["daily_limit"] > 0 and kid["spent_today"] + amt > kid["daily_limit"]:
                    st.error("Daily spending limit reached")
                else:
                    kid["balance"] -= amt
                    kid["spent_today"] += amt
                    add_tx(kid, "Sent via QR", amt, LOCAL_CURRENCY, amt)
                    rcv = st.session_state.kids[receiver]
                    rcv["balance"] += amt
                    add_tx(rcv, "Received via QR", amt, LOCAL_CURRENCY, amt)
                    notify(rcv, f"Received {amt:.2f} {LOCAL_CURRENCY} from {kid_choice} via QR")
                    st.success(f"Sent {amt:.2f} {LOCAL_CURRENCY} to {receiver}")
            except Exception as e:
                st.error(f"QR send failed: {e}")

# ====================== EXTERNAL TRANSFERS ======================
st.subheader("🏦 Transfer to Bank / Palmpay (Parent approval)")
if not st.session_state.parent_mode:
    st.info("Parent must be logged in to approve external transfers.")
else:
    xfer_tab1, xfer_tab2 = st.tabs(["Bank (Flutterwave)", "Palmpay (via Kora)"])

    with xfer_tab1:
        bank_code = st.text_input("Bank Code (e.g., 044 for Access Bank)")
        acct_no = st.text_input("Account Number")
        amt = st.number_input("Amount (NGN)", min_value=1.0, step=100.0, key="bank_amt")
        if st.button("Send via Flutterwave"):
            if amt > kid["balance"]:
                st.error("Not enough balance")
            elif kid["daily_limit"] > 0 and kid["spent_today"] + amt > kid["daily_limit"]:
                st.error("Daily spending limit reached")
            else:
                ref = f"MM-FLW-{kid_choice}-{dt.datetime.now().timestamp()}"
                resp = send_flutterwave_transfer(amt, acct_no, bank_code, ref)
                if str(resp.get("status")).lower() == "success":
                    kid["balance"] -= amt
                    kid["spent_today"] += amt
                    add_tx(kid, "Bank Transfer", amt, LOCAL_CURRENCY, amt)
                    notify(kid, f"Bank transfer successful: {amt:.2f} {LOCAL_CURRENCY}")
                    st.success("Transfer successful")
                else:
                    st.error(f"Failed: {resp}")
                    notify(kid, f"Bank transfer failed: {resp}")

    with xfer_tab2:
        palmpay_id = st.text_input("Palmpay Recipient ID")
        amt2 = st.number_input("Amount (NGN)", min_value=1.0, step=100.0, key="pp_amt")
        if st.button("Send to Palmpay"):
            if amt2 > kid["balance"]:
                st.error("Not enough balance")
            elif kid["daily_limit"] > 0 and kid["spent_today"] + amt2 > kid["daily_limit"]:
                st.error("Daily spending limit reached")
            else:
                ref = f"MM-KORA-{kid_choice}-{dt.datetime.now().timestamp()}"
                resp = send_kora_palmpay(amt2, palmpay_id, ref)
                if str(resp.get("status")).lower() == "success":
                    kid["balance"] -= amt2
                    kid["spent_today"] += amt2
                    add_tx(kid, "Palmpay Transfer", amt2, LOCAL_CURRENCY, amt2)
                    notify(kid, f"Palmpay transfer successful: {amt2:.2f} {LOCAL_CURRENCY}")
                    st.success("Transfer successful")
                else:
                    st.error(f"Failed: {resp}")
                    notify(kid, f"Palmpay transfer failed: {resp}")

# ====================== BALANCE & GOALS ======================
st.subheader("🏦 Account Summary")
st.metric(label=f"{kid_choice}'s Balance", value=f"{kid['balance']:.2f} {LOCAL_CURRENCY}")
st.caption(f"Daily Limit: {kid['daily_limit']:.2f} | Spent Today: {kid['spent_today']:.2f}")

st.subheader("🎯 Savings Goal")
g_name = st.text_input("Goal name", kid["goal_name"])
g_amt = st.number_input("Goal amount (NGN)", min_value=0.0, step=100.0, value=float(kid["goal_amount"]))
if st.button("Set Goal"):
    kid["goal_name"] = g_name
    kid["goal_amount"] = g_amt
    st.success("Goal updated")
if kid["goal_amount"] > 0:
    progress = min(kid["balance"] / kid["goal_amount"], 1.0) if kid["goal_amount"] else 0.0
    st.progress(progress)
    st.write(f"Saved {kid['balance']:.2f} / {kid['goal_amount']:.2f} for **{kid['goal_name']}**")
    if progress >= 1.0:
        st.balloons()
        st.success("🎉 Goal reached!")
        kid["badges"].add("🥇 Goal Achiever")

# ====================== REWARDS ======================
st.subheader("🏅 Rewards & Achievements")
st.write(f"⭐ Stars: **{kid['stars']}**")
if kid["badges"]:
    for b in kid["badges"]:
        st.success(b)
else:
    st.write("No badges yet. Keep saving!")

# ====================== HISTORY ======================
st.subheader("📜 Transaction History")
if kid["transactions"]:
    for tx in reversed(kid["transactions"]):
        t = tx["type"]
        line = f"{tx['date']} | {t}: {tx['converted']:.2f} {LOCAL_CURRENCY}"
        if t.startswith("Deposit"):
            st.success(line)
        elif t.startswith("Sent"):
            st.error(line)
        elif "Transfer" in t or t == "Withdrawal":
            st.error(line)
        elif "Received" in t or "Allowance" in t:
            st.info(line)
        else:
            st.write(line)
else:
    st.write("No transactions yet.")
