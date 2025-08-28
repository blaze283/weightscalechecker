import streamlit as st

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Kids Saving App",
    page_icon="🐷",
    layout="centered"
)

# ---------------- STATE ----------------
if "parent_pin" not in st.session_state:
    st.session_state.parent_pin = None
if "kids" not in st.session_state:
    st.session_state.kids = []
if "mode" not in st.session_state:
    st.session_state.mode = "home"
if "selected_kid" not in st.session_state:
    st.session_state.selected_kid = None

# ---------------- HOME ----------------
if st.session_state.mode == "home":
    st.title("🐷 Kids Saving App")
    st.caption("Simple savings manager for kids")

    if st.session_state.parent_pin:
        if st.button("Parent Login"):
            st.session_state.mode = "parent"
            st.rerun()
    else:
        if st.button("Set Parent PIN"):
            st.session_state.mode = "set_pin"
            st.rerun()

    if st.session_state.kids:
        if st.button("Kid Login"):
            st.session_state.mode = "kid_login"
            st.rerun()

# ---------------- SET PIN ----------------
elif st.session_state.mode == "set_pin":
    st.subheader("Set Parent PIN")
    pin = st.text_input("Enter a PIN", type="password")
    if st.button("Save"):
        if len(pin) >= 4:
            st.session_state.parent_pin = pin
            st.success("PIN set!")
            st.session_state.mode = "home"
            st.rerun()
        else:
            st.error("PIN must be 4+ digits")

# ---------------- PARENT ----------------
elif st.session_state.mode == "parent":
    st.subheader("Parent Dashboard")

    # Kids list
    st.write("### Children")
    if not st.session_state.kids:
        st.info("No kids added yet")
    else:
        for kid in st.session_state.kids:
            st.write(f"**{kid['name']}** — Balance: R{kid['balance']}")

    # Add kid
    st.write("### Add Kid")
    name = st.text_input("Child Name")
    allowance = st.number_input("Initial Savings", min_value=0, value=0)
    if st.button("Add Kid"):
        if not name:
            st.error("Enter child name")
        else:
            st.session_state.kids.append({"name": name, "balance": allowance})
            st.success("Kid added!")
            st.rerun()

    if st.button("Back"):
        st.session_state.mode = "home"
        st.rerun()

# ---------------- KID LOGIN ----------------
elif st.session_state.mode == "kid_login":
    st.subheader("Kid Login")
    names = [k["name"] for k in st.session_state.kids]
    choice = st.selectbox("Select your name", names if names else ["No kids yet"])
    if st.button("Login"):
        kid = next((k for k in st.session_state.kids if k["name"] == choice), None)
        if kid:
            st.session_state.selected_kid = kid
            st.session_state.mode = "kid"
            st.rerun()

    if st.button("Back"):
        st.session_state.mode = "home"
        st.rerun()

# ---------------- KID VIEW ----------------
elif st.session_state.mode == "kid":
    kid = st.session_state.selected_kid
    st.subheader(f"{kid['name']}'s Savings")
    st.write(f"Balance: R{kid['balance']}")

    if st.button("Back"):
        st.session_state.mode = "home"
        st.session_state.selected_kid = None
        st.rerun()
