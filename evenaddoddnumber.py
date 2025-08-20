import streamlit as st

# =================== DATA ===================
menu = {
    "Chicken Buckets": [
        {"id": "cb1", "name": "8 Pc Chicken Bucket", "desc": "8 pieces of KFC’s world-famous chicken.", "price": 14.99, "img": "https://i.imgur.com/hxhz3Hg.png"},
        {"id": "cb2", "name": "12 Pc Chicken Bucket", "desc": "12 pieces, perfect for family sharing.", "price": 19.99, "img": "https://i.imgur.com/hxhz3Hg.png"},
    ],
    "Burgers & Sandwiches": [
        {"id": "bg1", "name": "Zinger Burger", "desc": "Spicy crispy chicken fillet burger.", "price": 6.49, "img": "https://i.imgur.com/VW08x6S.png"},
        {"id": "bg2", "name": "Chicken Sandwich", "desc": "Juicy chicken breast on a toasted bun.", "price": 5.99, "img": "https://i.imgur.com/VW08x6S.png"},
    ],
    "Sides": [
        {"id": "sd1", "name": "Fries", "desc": "Golden crispy fries.", "price": 2.99, "img": "https://i.imgur.com/6rF0jAp.png"},
        {"id": "sd2", "name": "Coleslaw", "desc": "Fresh creamy coleslaw.", "price": 1.99, "img": "https://i.imgur.com/6rF0jAp.png"},
    ],
    "Drinks": [
        {"id": "dr1", "name": "Pepsi", "desc": "Refreshing soft drink.", "price": 1.49, "img": "https://i.imgur.com/Ed4xskj.png"},
        {"id": "dr2", "name": "Mountain Dew", "desc": "Citrus-flavored soda.", "price": 1.49, "img": "https://i.imgur.com/Ed4xskj.png"},
    ],
    "Desserts": [
        {"id": "ds1", "name": "Chocolate Cake", "desc": "Rich chocolate cake slice.", "price": 3.99, "img": "https://i.imgur.com/fdj52ZQ.png"},
        {"id": "ds2", "name": "Apple Pie", "desc": "Warm flaky crust apple pie.", "price": 2.99, "img": "https://i.imgur.com/fdj52ZQ.png"},
    ],
}

# =================== SESSION STATE ===================
if "cart" not in st.session_state:
    st.session_state.cart = {}

# =================== FUNCTIONS ===================
def add_to_cart(item):
    cart = st.session_state.cart
    if item["id"] in cart:
        cart[item["id"]]["quantity"] += 1
    else:
        cart[item["id"]] = {"name": item["name"], "price": item["price"], "quantity": 1}

def remove_from_cart(item_id):
    if item_id in st.session_state.cart:
        if st.session_state.cart[item_id]["quantity"] > 1:
            st.session_state.cart[item_id]["quantity"] -= 1
        else:
            del st.session_state.cart[item_id]

def checkout():
    st.success("✅ Order placed successfully! Your KFC meal is on the way 🚚🍗")
    st.session_state.cart.clear()

# =================== HEADER ===================
st.set_page_config(page_title="KFC Online Order", layout="wide")
st.title("🍗 KFC Online Ordering")

# =================== CART SIDEBAR ===================
with st.sidebar:
    st.header("🛒 Your Cart")
    if not st.session_state.cart:
        st.info("Cart is empty")
    else:
        total = 0
        for item_id, item in st.session_state.cart.items():
            st.write(f"**{item['name']}** x {item['quantity']}  —  ${item['price']*item['quantity']:.2f}")
            total += item["price"] * item["quantity"]
            if st.button(f"Remove {item['name']}", key="rm"+item_id):
                remove_from_cart(item_id)
        st.subheader(f"Total: ${total:.2f}")
        if st.button("✅ Checkout"):
            checkout()

# =================== MENU ===================
for category, items in menu.items():
    st.subheader(category)
    cols = st.columns(2)  # 2 items per row
    for i, item in enumerate(items):
        with cols[i % 2]:
            st.image(item["img"], width=150)
            st.write(f"**{item['name']}** - ${item['price']:.2f}")
            st.caption(item["desc"])
            if st.button(f"Add to Cart ({item['name']})", key=item["id"]):
                add_to_cart(item)
