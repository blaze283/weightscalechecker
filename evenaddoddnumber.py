import streamlit as st
from datetime import datetime, timedelta

# =================== PAGE CONFIG & STYLING ===================
st.set_page_config(
    page_title="KFC Online Order", 
    layout="wide",
    page_icon="🍗",
    initial_sidebar_state="expanded"
)

# Custom CSS for beautiful styling
st.markdown("""
<style>
    /* Main background and theme */
    .main {
        background: linear-gradient(135deg, #ff6b35 0%, #e63946 100%);
        color: white;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(90deg, #d62d20 0%, #ffa700 100%);
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    
    /* Category headers */
    .category-header {
        background: linear-gradient(45deg, #ffffff, #f8f9fa);
        color: #d62d20;
        padding: 1rem 2rem;
        border-radius: 25px;
        text-align: center;
        margin: 2rem 0 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #ffa700;
    }
    
    /* Menu item cards */
    .menu-item {
        background: white;
        color: #333;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        margin: 1rem 0;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        border: 2px solid transparent;
        height: 100%;
    }
    
    .menu-item:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 40px rgba(0,0,0,0.25);
        border-color: #ffa700;
    }
    
    /* Price styling */
    .price {
        color: #d62d20;
        font-size: 1.5rem;
        font-weight: bold;
    }
    
    /* Cart styling */
    .cart-header {
        background: linear-gradient(45deg, #d62d20, #ffa700);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .cart-item {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #d62d20;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(45deg, #d62d20, #ffa700);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 1.5rem;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 15px rgba(214, 45, 32, 0.4);
    }
    
    /* Metrics styling */
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    /* Success message styling */
    .success-message {
        background: linear-gradient(45deg, #28a745, #20c997);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        animation: pulse 2s infinite;
        margin: 1rem 0;
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    /* Filter section */
    .filter-section {
        background: rgba(255, 255, 255, 0.1);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    
    /* Badge styling */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        background: #ffa700;
        color: white;
        border-radius: 15px;
        font-size: 0.8rem;
        margin-right: 0.5rem;
    }
    
    .spicy-badge {
        background: #e63946;
    }
    
    /* Hide streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Custom spacing */
    .element-container {
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# =================== DATA WITH EXPANDED MENU ===================
menu = {
    "🍗 Chicken Buckets": [
        {
            "id": "cb1",
            "name": "8 Pc Chicken Bucket",
            "desc": "8 pieces of KFC's world-famous Original Recipe chicken with 11 herbs and spices.",
            "price": 14.99,
            "img": "https://i.ibb.co/vHwftMx/kfc-bucket.png",
            "popular": True,
            "spicy": False
        },
        {
            "id": "cb2",
            "name": "12 Pc Chicken Bucket",
            "desc": "12 pieces of finger lickin' good chicken, perfect for family sharing.",
            "price": 19.99,
            "img": "https://i.ibb.co/vHwftMx/kfc-bucket.png",
            "popular": False,
            "spicy": False
        },
        {
            "id": "cb3",
            "name": "16 Pc Party Bucket",
            "desc": "The ultimate party bucket with 16 pieces of delicious chicken.",
            "price": 24.99,
            "img": "https://i.ibb.co/vHwftMx/kfc-bucket.png",
            "popular": False,
            "spicy": False
        },
        {
            "id": "cb4",
            "name": "Hot Wings Bucket",
            "desc": "10 pieces of spicy hot wings that pack serious heat.",
            "price": 12.99,
            "img": "https://i.ibb.co/vHwftMx/kfc-bucket.png",
            "popular": True,
            "spicy": True
        },
    ],
    "🍔 Burgers & Sandwiches": [
        {
            "id": "bg1",
            "name": "Zinger Burger",
            "desc": "Spicy crispy chicken fillet with fresh lettuce and creamy mayo.",
            "price": 6.49,
            "img": "https://i.ibb.co/WpT1C4Y/kfc-burger.png",
            "popular": True,
            "spicy": True
        },
        {
            "id": "bg2",
            "name": "Original Recipe Burger",
            "desc": "Juicy chicken breast with Original Recipe coating on a toasted bun.",
            "price": 5.99,
            "img": "https://i.ibb.co/WpT1C4Y/kfc-burger.png",
            "popular": False,
            "spicy": False
        },
        {
            "id": "bg3",
            "name": "Hot & Spicy Burger",
            "desc": "Extra spicy chicken fillet that packs a punch with every bite.",
            "price": 6.99,
            "img": "https://i.ibb.co/WpT1C4Y/kfc-burger.png",
            "popular": False,
            "spicy": True
        },
        {
            "id": "bg4",
            "name": "Colonel's Club",
            "desc": "Premium chicken sandwich with bacon, cheese, and special sauce.",
            "price": 7.99,
            "img": "https://i.ibb.co/WpT1C4Y/kfc-burger.png",
            "popular": True,
            "spicy": False
        },
    ],
    "🍟 Sides": [
        {
            "id": "sd1",
            "name": "Regular Fries",
            "desc": "Golden crispy fries seasoned to perfection.",
            "price": 2.99,
            "img": "https://i.ibb.co/JjrBpM6/kfc-fries.png",
            "popular": True,
            "spicy": False
        },
        {
            "id": "sd2",
            "name": "Coleslaw",
            "desc": "Fresh and creamy coleslaw with a tangy dressing.",
            "price": 1.99,
            "img": "https://i.ibb.co/2sDqfLf/kfc-coleslaw.png",
            "popular": False,
            "spicy": False
        },
        {
            "id": "sd3",
            "name": "Mashed Potatoes",
            "desc": "Creamy mashed potatoes with rich gravy.",
            "price": 2.49,
            "img": "https://i.ibb.co/2sDqfLf/kfc-coleslaw.png",
            "popular": False,
            "spicy": False
        },
        {
            "id": "sd4",
            "name": "Spicy Wedges",
            "desc": "Crispy potato wedges with a spicy seasoning blend.",
            "price": 3.49,
            "img": "https://i.ibb.co/JjrBpM6/kfc-fries.png",
            "popular": True,
            "spicy": True
        },
    ],
    "🥤 Drinks": [
        {
            "id": "dr1",
            "name": "Pepsi",
            "desc": "Ice-cold refreshing Pepsi cola.",
            "price": 1.49,
            "img": "https://i.ibb.co/McKqgnh/pepsi.png",
            "popular": True,
            "spicy": False
        },
        {
            "id": "dr2",
            "name": "Mountain Dew",
            "desc": "Citrus-flavored energy boost in a bottle.",
            "price": 1.49,
            "img": "https://i.ibb.co/McKqgnh/pepsi.png",
            "popular": False,
            "spicy": False
        },
        {
            "id": "dr3",
            "name": "Fresh Orange Juice",
            "desc": "100% natural orange juice, freshly squeezed daily.",
            "price": 2.49,
            "img": "https://i.ibb.co/McKqgnh/pepsi.png",
            "popular": False,
            "spicy": False
        },
        {
            "id": "dr4",
            "name": "Iced Tea",
            "desc": "Refreshing sweet tea served over ice.",
            "price": 1.99,
            "img": "https://i.ibb.co/McKqgnh/pepsi.png",
            "popular": False,
            "spicy": False
        },
    ],
    "🍰 Desserts": [
        {
            "id": "ds1",
            "name": "Chocolate Cake",
            "desc": "Rich, moist chocolate cake with smooth chocolate frosting.",
            "price": 3.99,
            "img": "https://i.ibb.co/xLwC1p2/chocolate-cake.png",
            "popular": True,
            "spicy": False
        },
        {
            "id": "ds2",
            "name": "Apple Pie",
            "desc": "Warm flaky crust apple pie with cinnamon and spices.",
            "price": 2.99,
            "img": "https://i.ibb.co/xLwC1p2/chocolate-cake.png",
            "popular": False,
            "spicy": False
        },
        {
            "id": "ds3",
            "name": "Ice Cream Sundae",
            "desc": "Vanilla ice cream with hot fudge sauce and chopped nuts.",
            "price": 3.49,
            "img": "https://i.ibb.co/xLwC1p2/chocolate-cake.png",
            "popular": False,
            "spicy": False
        },
        {
            "id": "ds4",
            "name": "Cookies & Cream",
            "desc": "Creamy cookies and cream dessert with chocolate crumbles.",
            "price": 2.79,
            "img": "https://i.ibb.co/xLwC1p2/chocolate-cake.png",
            "popular": True,
            "spicy": False
        },
    ],
}

# =================== SESSION STATE ===================
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "customer_name" not in st.session_state:
    st.session_state.customer_name = ""
if "customer_phone" not in st.session_state:
    st.session_state.customer_phone = ""
if "order_placed" not in st.session_state:
    st.session_state.order_placed = False
if "order_history" not in st.session_state:
    st.session_state.order_history = []

# =================== FUNCTIONS ===================
def add_to_cart(item):
    cart = st.session_state.cart
    if item["id"] in cart:
        cart[item["id"]]["quantity"] += 1
    else:
        cart[item["id"]] = {
            "name": item["name"],
            "price": item["price"],
            "quantity": 1,
        }
    st.success(f"✅ Added {item['name']} to cart!")

def remove_from_cart(item_id):
    if item_id in st.session_state.cart:
        if st.session_state.cart[item_id]["quantity"] > 1:
            st.session_state.cart[item_id]["quantity"] -= 1
        else:
            del st.session_state.cart[item_id]

def clear_cart():
    st.session_state.cart.clear()

def checkout():
    if st.session_state.customer_name.strip() and st.session_state.customer_phone.strip():
        order_id = f"KFC{datetime.now().strftime('%H%M%S')}"
        delivery_time = datetime.now() + timedelta(minutes=25)
        
        # Save order to history
        order_summary = {
            "order_id": order_id,
            "customer": st.session_state.customer_name,
            "phone": st.session_state.customer_phone,
            "items": dict(st.session_state.cart),
            "total": get_final_total(),
            "timestamp": datetime.now(),
            "delivery_time": delivery_time
        }
        st.session_state.order_history.append(order_summary)
        
        st.markdown(f"""
        <div class="success-message">
            <h2>🎉 Order Confirmed!</h2>
            <p><strong>Thank you {st.session_state.customer_name}!</strong></p>
            <p>Your delicious KFC meal is being prepared 👨‍🍳</p>
            <p><strong>Order ID:</strong> #{order_id}</p>
            <p><strong>Phone:</strong> {st.session_state.customer_phone}</p>
            <p><strong>Estimated delivery:</strong> {delivery_time.strftime('%I:%M %p')}</p>
            <p><strong>Total amount:</strong> ${get_final_total():.2f}</p>
            <p>🚚 Your order is now being prepared with love!</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.balloons()
        st.session_state.cart.clear()
        st.session_state.order_placed = True
    else:
        st.error("Please enter both your name and phone number before checkout!")

def get_cart_total():
    return sum(item["price"] * item["quantity"] for item in st.session_state.cart.values())

def get_cart_count():
    return sum(item["quantity"] for item in st.session_state.cart.values())

def get_delivery_fee():
    total = get_cart_total()
    return 2.99 if total < 20 else 0

def get_tax():
    return get_cart_total() * 0.08

def get_final_total():
    return get_cart_total() + get_delivery_fee() + get_tax()

# =================== HEADER ===================
st.markdown("""
<div class="main-header">
    <h1>🍗 Kentucky Fried Chicken</h1>
    <h3>Finger Lickin' Good! 🔥</h3>
    <p>Order online for fast delivery • Fresh • Hot • Delicious</p>
    <p>📍 Serving Lagos, Nigeria | 🕒 Open 24/7 | 📞 1-800-CALL-KFC</p>
</div>
""", unsafe_allow_html=True)

# =================== METRICS ROW ===================
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🛒 Items in Cart", get_cart_count())
with col2:
    st.metric("💰 Cart Total", f"${get_cart_total():.2f}")
with col3:
    st.metric("🚚 Delivery Time", "25 min")
with col4:
    st.metric("⭐ Rating", "4.8/5")

# =================== CART SIDEBAR ===================
with st.sidebar:
    st.markdown('<div class="cart-header"><h2>🛒 Your Order</h2></div>', unsafe_allow_html=True)
    
    # Customer information
    st.markdown("**📝 Customer Information**")
    st.session_state.customer_name = st.text_input("👤 Full Name", value=st.session_state.customer_name, placeholder="Enter your full name")
    st.session_state.customer_phone = st.text_input("📱 Phone Number", value=st.session_state.customer_phone, placeholder="Enter your phone number")
    
    st.markdown("---")
    
    if not st.session_state.cart:
        st.info("🍗 Your cart is empty\n\nStart adding some finger lickin' good items!")
        st.markdown("### 🎯 **Today's Specials**")
        st.success("🔥 **Free delivery** on orders over $20!")
        st.info("⭐ **Most Popular:** Zinger Burger & 8 Pc Bucket")
    else:
        st.markdown("**🛍️ Order Summary**")
        total = 0
        for item_id, item in st.session_state.cart.items():
            with st.container():
                st.markdown(f"""
                <div class="cart-item">
                    <strong>{item['name']}</strong><br>
                    <small>Quantity: {item['quantity']} × ${item['price']:.2f}</small><br>
                    <span class="price">${item['price']*item['quantity']:.2f}</span>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([1,1,1])
                with col1:
                    if st.button("➖", key="minus"+item_id, help="Remove one"):
                        remove_from_cart(item_id)
                        st.rerun()
                with col2:
                    st.write(f"**{item['quantity']}**")
                with col3:
                    if st.button("➕", key="plus"+item_id, help="Add one"):
                        st.session_state.cart[item_id]["quantity"] += 1
                        st.rerun()
                
                total += item["price"] * item["quantity"]
        
        st.markdown("---")
        
        # Pricing breakdown
        delivery_fee = get_delivery_fee()
        tax = get_tax()
        final_total = get_final_total()
        
        st.markdown("**💰 Pricing Breakdown**")
        st.write(f"Subtotal: ${total:.2f}")
        st.write(f"Delivery: ${delivery_fee:.2f} {'🎉 FREE!' if delivery_fee == 0 else ''}")
        st.write(f"Tax (8%): ${tax:.2f}")
        st.markdown(f"### **Final Total: ${final_total:.2f}**")
        
        # Progress bar for free delivery
        if total < 20:
            remaining = 20 - total
            progress = total / 20
            st.progress(progress)
            st.caption(f"Add ${remaining:.2f} more for FREE delivery! 🚚")
        else:
            st.success("🎉 You qualify for FREE delivery!")
        
        st.markdown("---")
        
        # Action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear Cart", use_container_width=True):
                clear_cart()
                st.rerun()
        with col2:
            if st.button("✅ Place Order", type="primary", use_container_width=True):
                checkout()
        
        st.markdown("---")
        st.info("🕐 **Delivery Info:**\n• Average delivery time: 25 min\n• Contact: 1-800-CALL-KFC\n• We deliver 24/7 in Lagos!")

# =================== ORDER HISTORY (if any) ===================
if st.session_state.order_history:
    with st.expander("📜 Order History"):
        for order in reversed(st.session_state.order_history[-3:]):  # Show last 3 orders
            st.markdown(f"""
            **Order #{order['order_id']}** - {order['timestamp'].strftime('%Y-%m-%d %I:%M %p')}
            - Customer: {order['customer']}
            - Total: ${order['total']:.2f}
            - Items: {len(order['items'])} items
            """)

# =================== MENU FILTERS ===================
st.markdown("---")
st.markdown("### 🔍 **Menu Filters**")
col1, col2, col3 = st.columns(3)
with col1:
    show_popular = st.checkbox("⭐ Popular items only", value=False)
with col2:
    show_spicy = st.checkbox("🌶️ Spicy items only", value=False)
with col3:
    price_filter = st.selectbox("💰 Price Range", ["All Prices", "Under $5", "$5-$10", "Over $10"])

# =================== MENU DISPLAY ===================
for category, items in menu.items():
    # Filter items based on checkboxes and price
    filtered_items = items
    if show_popular:
        filtered_items = [item for item in filtered_items if item.get("popular", False)]
    if show_spicy:
        filtered_items = [item for item in filtered_items if item.get("spicy", False)]
    
    # Price filtering
    if price_filter == "Under $5":
        filtered_items = [item for item in filtered_items if item["price"] < 5]
    elif price_filter == "$5-$10":
        filtered_items = [item for item in filtered_items if 5 <= item["price"] <= 10]
    elif price_filter == "Over $10":
        filtered_items = [item for item in filtered_items if item["price"] > 10]
    
    if filtered_items:  # Only show category if it has items after filtering
        st.markdown(f"""
        <div class="category-header">
            <h2>{category}</h2>
            <p>{len(filtered_items)} item{'s' if len(filtered_items) != 1 else ''} available</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Create responsive grid (2 columns for better mobile experience)
        cols = st.columns(2)
        for i, item in enumerate(filtered_items):
            with cols[i % 2]:
                with st.container():
                    st.markdown('<div class="menu-item">', unsafe_allow_html=True)
                    
                    # Image with aspect ratio
                    st.image(item["img"], use_column_width=True)
                    
                    # Title with badges
                    badges_html = ""
                    if item.get("popular"):
                        badges_html += '<span class="badge">⭐ Popular</span>'
                    if item.get("spicy"):
                        badges_html += '<span class="badge spicy-badge">🌶️ Spicy</span>'
                    
                    st.markdown(f"### {item['name']}")
                    if badges_html:
                        st.markdown(badges_html, unsafe_allow_html=True)
                    
                    # Price
                    st.markdown(f'<div class="price">${item["price"]:.2f}</div>', unsafe_allow_html=True)
                    
                    # Description
                    st.write(item["desc"])
                    
                    # Add to cart button with quantity in cart
                    cart_qty = st.session_state.cart.get(item["id"], {}).get("quantity", 0)
                    button_text = f"🛒 Add to Cart" + (f" ({cart_qty} in cart)" if cart_qty > 0 else "")
                    
                    if st.button(button_text, key=f"add_{item['id']}", use_container_width=True):
                        add_to_cart(item)
                        st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)

# =================== PROMOTIONAL SECTION ===================
st.markdown("---")
st.markdown("### 🎉 **Current Promotions**")
col1, col2, col3 = st.columns(3)
with col1:
    st.info("🍟 **Free Fries** with any bucket order!")
with col2:
    st.success("🚚 **Free Delivery** on orders over $20!")
with col3:
    st.warning("🌶️ **Spicy Special:** 20% off all spicy items!")

# =================== FOOTER ===================
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 2rem; background: linear-gradient(45deg, #d62d20, #ffa700); border-radius: 15px; color: white; margin-top: 2rem;">
    <h2>🍗 Kentucky Fried Chicken</h2>
    <h4>"It's Finger Lickin' Good!" ✨</h4>
    
    <div style="margin: 1.5rem 0;">
        <p><strong>📞 Order Hotline:</strong> 1-800-CALL-KFC</p>
        <p><strong>🌐 Website:</strong> kfc.com</p>
        <p><strong>📍 Location:</strong> Lagos, Nigeria</p>
        <p><strong>🕒 Hours:</strong> Open 24/7</p>
    </div>
    
    <div style="margin: 1rem 0;">
        <strong>Follow us on social media:</strong><br>
        📘 Facebook | 📷 Instagram | 🐦 Twitter | 📺 YouTube
    </div>
    
    <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.3);">
        <p><small>© 2025 KFC Corporation. All rights reserved. | Made with ❤️ for our customers</small></p>
    </div>
</div>
""", unsafe_allow_html=True)

# Add some spacing at the bottom
st.markdown("<br><br>", unsafe_allow_html=True)
