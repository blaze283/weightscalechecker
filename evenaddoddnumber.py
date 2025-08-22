import streamlit as st
import subprocess
import platform

st.set_page_config(page_title="WiFi Network Scanner", page_icon="📡", layout="centered")

st.title("📡 Nearby Wi-Fi Networks")

# Detect OS
system = platform.system()

def scan_wifi():
    networks = []
    if system == "Linux" or system == "Darwin":  # macOS uses Darwin
        result = subprocess.run(["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi"], capture_output=True, text=True)
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split(":")
                if len(parts) == 2:
                    ssid, signal = parts
                    networks.append({"SSID": ssid, "Signal": signal})
    elif system == "Windows":
        result = subprocess.run(["netsh", "wlan", "show", "networks", "mode=bssid"], capture_output=True, text=True)
        ssid = None
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("SSID"):
                ssid = line.split(":", 1)[1].strip()
            elif line.startswith("Signal") and ssid:
                signal = line.split(":", 1)[1].strip()
                networks.append({"SSID": ssid, "Signal": signal})
                ssid = None
    return networks

# Scan button
if st.button("🔍 Scan Networks"):
    wifi_list = scan_wifi()
    if wifi_list:
        st.subheader("Available Wi-Fi Networks")
        for net in wifi_list:
            st.write(f"📶 **{net['SSID']}** — Signal: {net['Signal']}%")
    else:
        st.warning("No Wi-Fi networks found.")

# Optional: Try connecting (only for your own Wi-Fi!)
st.subheader("🔑 Connect to Wi-Fi")
ssid = st.text_input("Enter Wi-Fi Name (SSID)")
password = st.text_input("Enter Password", type="password")

if st.button("Connect"):
    if system == "Linux" or system == "Darwin":
        result = subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password], capture_output=True, text=True)
    elif system == "Windows":
        result = subprocess.run(["netsh", "wlan", "connect", f"name={ssid}"], capture_output=True, text=True)
    else:
        result = None

    if result and "successfully" in result.stdout.lower():
        st.success(f"✅ Connected to {ssid}")
    else:
        st.error(f"❌ Failed to connect to {ssid}. Wrong password or network issue.")
