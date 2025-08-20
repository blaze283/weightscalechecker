import streamlit as st

# =================== DATA ===================
restaurants = [
    {
        "id": "1",
        "name": "Mama's Italian Kitchen",
        "cuisine": "Italian • Pizza • Pasta",
        "rating": 4.8,
        "delivery_time": "25-35 min",
        "delivery_fee": "Free",
    },
    {
        "id": "2",
        "name": "Tokyo Sushi Bar",
        "cuisine": "Japanese • Sushi • Asian",
        "rating": 4.7,
        "delivery_time": "30-40 min",
        "delivery_fee": "$2.99",
    },
    {
        "id": "3",
        "name": "El Mariachi",
        "cuisine": "Mexican • Tacos • Burritos",
        "rating": 4.6,
        "delivery_time": "20-30 min",
        "delivery_fee": "$1.99",
    },
]

menu_items = {
    "1": [
        {"id": "item-1", "name": "Margherita Pizza", "desc": "Fresh mozzarella, tomato sauce, basil", "price": 16.99},
        {"id": "item-2", "name": "Spaghetti Carbonara", "desc": "Pasta with eggs, pecorino, pancetta", "price": 18.99},
        {"id": "item-3", "name": "Chicken Parmigiana", "desc": "Breaded chicken with marinara sauce", "price": 22.99},
    ],
    "2": [
        {"id": "item-5", "name": "Salmon Sashimi", "desc": "Fresh Atlantic salmon", "price": 24.99},
        {"id": "item-6", "name": "Dragon Roll", "desc": "Shrimp tempura, avocado, eel, spicy mayo", "price": 18.99},
        {"id": "item-7", "name": "Chicken Teriyaki Bowl", "desc": "Grilled chicken, rice, veggies", "price": 16.99},
    ],
    "3": [
        {"id": "item-9", "name": "Carne Asada Tacos", "desc": "Grilled steak, onions, cilantro", "price": 14.99},
        {"id": "item-10", "name": "Chicken Burrito Bowl", "desc": "Chicken, rice, beans, pico de gallo", "price": 13.99},
        {"id": "item-11", "name": "Veggie Quesadilla", "desc": "Bell peppers, onions, mushrooms", "price": 11.99},
    ],
}

# =================== SESSION STATE ===================
if "selected_restaurant" not in st.session_state:
    st.session_state.selected_restaurant = None

if "cart" not in st.session_state:
    st.session_state.cart = {}

# =================== FUNCTIONS ===================
def add_to_cart(item):
    cart = st.session_state.cart
    if item["id"] in cart:
        cart[item["id"]]["quantity"] += 1
    else:
        cart[item["id"]] = {"name": item["name"], "price": item["price"], "quantity": 1}

def remove_from_cart(item):
    cart = st.session_state.cart
    if item["id"] in cart:
        if cart[item["id"]]["quantity"] > 1:
            cart[item["id"]]["quantity"] -= 1
        else:
            del cart[item["id"]]

def checkout():
    st.success("✅ Order placed! Your food is on the way 🚚🍴")
    st.session_state.cart.clear()
    st.session_state.selected_restaurant = None

# =================== UI ===================
st.title("🍽️ Food Delivery App")

# CART SUMMARY BUTTON
cart_count = sum(item["quantity"] for item in st.session_state.cart.values())
if cart_count > 0:
    if st.button(f"🛒 Cart ({cart_count})"):
        st.session_state.selected_restaurant = "cart"

# ----------------- CART PAGE -----------------
if st.session_state.selected_restaurant == "cart":
    st.header("🛒 Your Cart")
    if not st.session_state.cart:
        st.info("Your cart is empty.")
    else:
        total = 0
        for item in st.session_state.cart.values():
            st.write(f"{item['name']} - ${item['price']} x {item['quantity']}")
            total += item["price"] * item["quantity"]
        st.subheader(f"Total: ${total:.2f}")
        if st.button("✅ Checkout"):
            checkout()
    if st.button("⬅️ Continue Shopping"):
        st.session_state.selected_restaurant = None

# ----------------- MENU PAGE -----------------
elif st.session_state.selected_restaurant:
    restaurant = next(r for r in restaurants if r["id"] == st.session_state.selected_restaurant)
    st.header(restaurant["name"])
    st.caption(f"{restaurant['cuisine']} | ⭐ {restaurant['rating']} | ⏱ {restaurant['delivery_time']} | {restaurant['delivery_fee']}")

    for item in menu_items[restaurant["id"]]:
        col1, col2 = st.columns([3,1])
        with col1:
            st.write(f"**{item['name']}** - ${item['price']}")
            st.caption(item["desc"])
        with col2:
            if st.button(f"Add {item['id']}", key=item["id"]):
                add_to_cart(item)
            if item["id"] in st.session_state.cart:
                qty = st.session_state.cart[item["id"]]["quantity"]
                st.write(f"Qty: {qty}")
                if st.button(f"Remove {item['id']}", key=item["id"]+"remove"):
                    remove_from_cart(item)

    if st.button("⬅️ Back to Restaurants"):
        st.session_state.selected_restaurant = None

# ----------------- RESTAURANTS PAGE -----------------
else:
    st.subheader("🍴 Popular Restaurants")
    for r in restaurants:
        if st.button(r["name"], key=r["id"]):
            st.session_state.selected_restaurant = r["id"]
