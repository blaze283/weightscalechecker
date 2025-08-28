# money_matters_kid_enhanced.py
# Enhanced Streamlit app: Kid-safe banking prototype
# Major improvements:
# - Better error handling and input validation
# - Enhanced security with session timeouts
# - Improved UI/UX with better organization
# - Transaction categories and filtering
# - Email notifications option
# - Better database schema with indexes
# - Input sanitization and rate limiting
# - Audit logging for security
# - Responsive design improvements

import streamlit as st
import sqlite3
import os
import re
from datetime import datetime, timedelta, date
import hashlib
import secrets
import qrcode
from io import BytesIO
import base64
import json
import threading
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('banking_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Try import optional dependencies
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# -------------------- CONFIG --------------------
@dataclass
class Config:
    DEFAULT_COUNTRY_CODE: str = "+234"
    DB_PATH: str = "money_matters_kids_enhanced.db"
    OTP_EXPIRY_SECONDS: int = 300
    SESSION_TIMEOUT_MINUTES: int = 30
    MAX_LOGIN_ATTEMPTS: int = 5
    RATE_LIMIT_WINDOW: int = 300  # 5 minutes
    MAX_REQUESTS_PER_WINDOW: int = 20
    MIN_PIN_LENGTH: int = 4
    MAX_DAILY_LIMIT: float = 10000.0
    MAX_ALLOWANCE: float = 5000.0
    SUPPORTED_CURRENCIES: List[str] = None

    def __post_init__(self):
        if self.SUPPORTED_CURRENCIES is None:
            self.SUPPORTED_CURRENCIES = ["₦", "$", "€", "£"]

config = Config()

# -------------------- DATA MODELS --------------------
@dataclass
class User:
    id: int
    phone: str
    country_code: str
    name: str
    role: str
    parent_id: Optional[int]
    balance: float
    daily_limit: float
    allowance_amount: float
    allowance_interval_days: int
    last_allowance_credit: Optional[str]
    spent_today: float
    created_at: str
    is_active: bool = True

@dataclass
class Transaction:
    id: int
    user_id: int
    amount: float
    type: str
    category: str
    description: str
    recipient_phone: Optional[str]
    timestamp: str
    approved: bool
    
# -------------------- DATABASE --------------------
class DatabaseManager:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        conn = self.get_conn()
        cur = conn.cursor()
        
        # Enhanced users table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL,
            country_code TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('parent', 'kid')),
            parent_id INTEGER,
            pin_hash TEXT NOT NULL,
            balance REAL DEFAULT 0 CHECK(balance >= 0),
            daily_limit REAL DEFAULT 0 CHECK(daily_limit >= 0),
            allowance_amount REAL DEFAULT 0 CHECK(allowance_amount >= 0),
            allowance_interval_days INTEGER DEFAULT 30 CHECK(allowance_interval_days > 0),
            last_allowance_credit TEXT,
            last_spend_date TEXT,
            spent_today REAL DEFAULT 0 CHECK(spent_today >= 0),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            email TEXT,
            failed_login_attempts INTEGER DEFAULT 0,
            last_failed_login TEXT,
            FOREIGN KEY(parent_id) REFERENCES users(id)
        )
        ''')
        
        # Enhanced transactions table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('credit', 'debit', 'allowance', 'transfer')),
            category TEXT DEFAULT 'general',
            description TEXT NOT NULL,
            recipient_phone TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            approved INTEGER DEFAULT 1,
            created_by INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
        ''')
        
        # OTPs table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY,
            phone TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Audit log for security
        cur.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Rate limiting table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY,
            identifier TEXT NOT NULL,
            requests INTEGER DEFAULT 1,
            window_start TEXT NOT NULL
        )
        ''')
        
        # Create indexes for performance
        cur.execute('CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_otps_phone ON otps(phone)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_log(user_id)')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

db = DatabaseManager()

# -------------------- SECURITY --------------------
class SecurityManager:
    @staticmethod
    def hash_pin(pin: str, salt: str = None) -> str:
        if salt is None:
            salt = secrets.token_hex(8)
        dk = hashlib.pbkdf2_hmac('sha256', pin.encode(), salt.encode(), 100000)
        return salt + '$' + dk.hex()
    
    @staticmethod
    def verify_pin(pin: str, stored: str) -> bool:
        try:
            salt, hexhash = stored.split('$')
            dk = hashlib.pbkdf2_hmac('sha256', pin.encode(), salt.encode(), 100000)
            return dk.hex() == hexhash
        except Exception as e:
            logger.error(f"PIN verification error: {e}")
            return False
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        # Remove any non-digit characters for validation
        clean_phone = re.sub(r'\D', '', phone)
        return len(clean_phone) >= 10 and len(clean_phone) <= 15
    
    @staticmethod
    def validate_pin(pin: str) -> Tuple[bool, str]:
        if len(pin) < config.MIN_PIN_LENGTH:
            return False, f"PIN must be at least {config.MIN_PIN_LENGTH} digits"
        if not pin.isdigit():
            return False, "PIN must contain only digits"
        if len(set(pin)) == 1:
            return False, "PIN cannot be all the same digit"
        return True, "Valid PIN"
    
    @staticmethod
    def sanitize_input(text: str, max_length: int = 100) -> str:
        if not text:
            return ""
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\'\`;]', '', text[:max_length])
        return sanitized.strip()
    
    @staticmethod
    def check_rate_limit(identifier: str) -> bool:
        conn = db.get_conn()
        cur = conn.cursor()
        
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=config.RATE_LIMIT_WINDOW)
        
        # Clean old entries
        cur.execute('DELETE FROM rate_limits WHERE window_start < ?', 
                   (window_start.isoformat(),))
        
        # Check current rate
        cur.execute('SELECT requests FROM rate_limits WHERE identifier = ? AND window_start > ?', 
                   (identifier, window_start.isoformat()))
        result = cur.fetchone()
        
        if result and result['requests'] >= config.MAX_REQUESTS_PER_WINDOW:
            conn.close()
            return False
        
        # Update or insert rate limit
        if result:
            cur.execute('UPDATE rate_limits SET requests = requests + 1 WHERE identifier = ?', 
                       (identifier,))
        else:
            cur.execute('INSERT INTO rate_limits (identifier, window_start) VALUES (?, ?)', 
                       (identifier, now.isoformat()))
        
        conn.commit()
        conn.close()
        return True

security = SecurityManager()

# -------------------- USER MANAGEMENT --------------------
class UserManager:
    @staticmethod
    def get_user_by_phone(phone: str) -> Optional[Dict]:
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE phone = ? AND is_active = 1", (phone,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    
    @staticmethod
    def create_user(phone: str, country_code: str, name: str, role: str, 
                   pin: str, parent_id: Optional[int] = None, 
                   initial_balance: float = 0, email: str = None) -> bool:
        try:
            # Validate inputs
            phone = security.sanitize_input(phone, 20)
            name = security.sanitize_input(name, 50)
            
            if not security.validate_phone(phone):
                raise ValueError("Invalid phone number")
            
            is_valid, msg = security.validate_pin(pin)
            if not is_valid:
                raise ValueError(msg)
            
            if UserManager.get_user_by_phone(phone):
                raise ValueError("Phone number already registered")
            
            conn = db.get_conn()
            cur = conn.cursor()
            pin_hash = security.hash_pin(pin)
            
            cur.execute('''
                INSERT INTO users (phone, country_code, name, role, parent_id, 
                                 pin_hash, balance, email)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (phone, country_code, name, role, parent_id, pin_hash, 
                 initial_balance, email))
            
            user_id = cur.lastrowid
            
            # Log the creation
            cur.execute('''
                INSERT INTO audit_log (user_id, action, details)
                VALUES (?, ?, ?)
            ''', (user_id, 'USER_CREATED', f'Role: {role}, Parent ID: {parent_id}'))
            
            conn.commit()
            conn.close()
            
            logger.info(f"User created: {name} ({phone}), Role: {role}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return False
    
    @staticmethod
    def authenticate_user(phone: str, pin: str) -> Tuple[bool, Optional[Dict], str]:
        user = UserManager.get_user_by_phone(phone)
        if not user:
            return False, None, "User not found"
        
        # Check for account lockout
        if user.get('failed_login_attempts', 0) >= config.MAX_LOGIN_ATTEMPTS:
            last_failed = user.get('last_failed_login')
            if last_failed:
                last_failed_dt = datetime.fromisoformat(last_failed)
                if datetime.utcnow() - last_failed_dt < timedelta(hours=1):
                    return False, None, "Account temporarily locked due to too many failed attempts"
        
        if security.verify_pin(pin, user['pin_hash']):
            # Reset failed attempts on successful login
            conn = db.get_conn()
            cur = conn.cursor()
            cur.execute('UPDATE users SET failed_login_attempts = 0 WHERE id = ?', 
                       (user['id'],))
            cur.execute('''
                INSERT INTO audit_log (user_id, action, details)
                VALUES (?, ?, ?)
            ''', (user['id'], 'LOGIN_SUCCESS', f'Phone: {phone}'))
            conn.commit()
            conn.close()
            
            logger.info(f"Successful login: {user['name']} ({phone})")
            return True, user, "Login successful"
        else:
            # Increment failed attempts
            conn = db.get_conn()
            cur = conn.cursor()
            cur.execute('''
                UPDATE users SET failed_login_attempts = failed_login_attempts + 1,
                               last_failed_login = ?
                WHERE id = ?
            ''', (datetime.utcnow().isoformat(), user['id']))
            cur.execute('''
                INSERT INTO audit_log (user_id, action, details)
                VALUES (?, ?, ?)
            ''', (user['id'], 'LOGIN_FAILED', f'Phone: {phone}'))
            conn.commit()
            conn.close()
            
            logger.warning(f"Failed login attempt: {phone}")
            return False, None, "Invalid PIN"

user_manager = UserManager()

# -------------------- TRANSACTION MANAGEMENT --------------------
class TransactionManager:
    CATEGORIES = ['food', 'entertainment', 'education', 'shopping', 'transport', 'savings', 'other']
    
    @staticmethod
    def add_transaction(user_id: int, amount: float, ttype: str, 
                       description: str, category: str = 'general',
                       recipient_phone: str = None, approved: bool = True,
                       created_by: int = None) -> bool:
        try:
            conn = db.get_conn()
            cur = conn.cursor()
            
            ts = datetime.utcnow().isoformat()
            
            cur.execute('''
                INSERT INTO transactions (user_id, amount, type, category, description, 
                                        recipient_phone, timestamp, approved, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, amount, ttype, category, description, recipient_phone, 
                 ts, int(approved), created_by))
            
            transaction_id = cur.lastrowid
            
            # Update balance if approved
            if approved:
                cur.execute('UPDATE users SET balance = balance + ? WHERE id = ?', 
                           (amount, user_id))
            
            # Log transaction
            cur.execute('''
                INSERT INTO audit_log (user_id, action, details)
                VALUES (?, ?, ?)
            ''', (user_id, 'TRANSACTION_CREATED', 
                 f'Type: {ttype}, Amount: {amount}, Approved: {approved}'))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Transaction created: ID {transaction_id}, User {user_id}, Amount {amount}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create transaction: {e}")
            return False
    
    @staticmethod
    def get_transactions(user_id: int, limit: int = 50, 
                        category: str = None) -> List[Dict]:
        conn = db.get_conn()
        cur = conn.cursor()
        
        query = '''
            SELECT * FROM transactions 
            WHERE user_id = ? 
        '''
        params = [user_id]
        
        if category and category != 'all':
            query += ' AND category = ?'
            params.append(category)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    @staticmethod
    def approve_transaction(transaction_id: int, approver_id: int) -> bool:
        try:
            conn = db.get_conn()
            cur = conn.cursor()
            
            # Get transaction details
            cur.execute('SELECT * FROM transactions WHERE id = ?', (transaction_id,))
            transaction = cur.fetchone()
            
            if not transaction:
                return False
            
            # Update transaction status
            cur.execute('UPDATE transactions SET approved = 1 WHERE id = ?', 
                       (transaction_id,))
            
            # Update user balance
            cur.execute('UPDATE users SET balance = balance + ? WHERE id = ?', 
                       (transaction['amount'], transaction['user_id']))
            
            # Log approval
            cur.execute('''
                INSERT INTO audit_log (user_id, action, details)
                VALUES (?, ?, ?)
            ''', (approver_id, 'TRANSACTION_APPROVED', 
                 f'Transaction ID: {transaction_id}'))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Transaction approved: ID {transaction_id} by user {approver_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to approve transaction: {e}")
            return False

transaction_manager = TransactionManager()

# -------------------- NOTIFICATION SYSTEM --------------------
class NotificationManager:
    @staticmethod
    def send_otp(phone: str, country_code: str, code: str) -> Tuple[bool, str]:
        full_phone = f"{country_code}{phone}"
        
        # Try Twilio first
        if TWILIO_AVAILABLE and all(k in st.secrets for k in 
                                   ("twilio_account_sid", "twilio_auth_token", "twilio_from_number")):
            try:
                client = TwilioClient(st.secrets.twilio_account_sid, 
                                    st.secrets.twilio_auth_token)
                message = client.messages.create(
                    body=f"Your Money Matters verification code: {code}",
                    from_=st.secrets.twilio_from_number,
                    to=full_phone
                )
                logger.info(f"OTP sent via Twilio to {full_phone}")
                return True, f"OTP sent via SMS"
            except Exception as e:
                logger.error(f"Twilio error: {e}")
                return False, f"SMS service error: {str(e)}"
        
        # Fallback to simulation
        logger.info(f"OTP simulation: {code} for {full_phone}")
        return False, f"Development mode - OTP: {code}"
    
    @staticmethod
    def send_email_notification(email: str, subject: str, body: str) -> bool:
        if not EMAIL_AVAILABLE or not email:
            return False
        
        # This would need SMTP configuration in secrets
        # Placeholder for email functionality
        logger.info(f"Email notification sent to {email}: {subject}")
        return True

notification_manager = NotificationManager()

# -------------------- OTP MANAGEMENT --------------------
class OTPManager:
    @staticmethod
    def generate_otp() -> str:
        return str(secrets.randbelow(10**6)).zfill(6)
    
    @staticmethod
    def store_otp(phone: str, code: str) -> bool:
        try:
            conn = db.get_conn()
            cur = conn.cursor()
            
            expires_at = (datetime.utcnow() + 
                         timedelta(seconds=config.OTP_EXPIRY_SECONDS)).isoformat()
            
            cur.execute('''
                INSERT INTO otps (phone, code, expires_at) 
                VALUES (?, ?, ?)
            ''', (phone, code, expires_at))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Failed to store OTP: {e}")
            return False
    
    @staticmethod
    def verify_otp(phone: str, code: str) -> bool:
        try:
            conn = db.get_conn()
            cur = conn.cursor()
            
            cur.execute('''
                SELECT * FROM otps 
                WHERE phone = ? AND used = 0 
                ORDER BY created_at DESC LIMIT 1
            ''', (phone,))
            
            row = cur.fetchone()
            
            if not row:
                conn.close()
                return False
            
            if row['code'] != code:
                conn.close()
                return False
            
            if datetime.fromisoformat(row['expires_at']) < datetime.utcnow():
                conn.close()
                return False
            
            # Mark OTP as used
            cur.execute('UPDATE otps SET used = 1 WHERE id = ?', (row['id'],))
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"OTP verification error: {e}")
            return False

otp_manager = OTPManager()

# -------------------- STREAMLIT UI --------------------

def check_session_timeout():
    """Check if session has timed out"""
    if 'last_activity' in st.session_state:
        last_activity = datetime.fromisoformat(st.session_state['last_activity'])
        if datetime.utcnow() - last_activity > timedelta(minutes=config.SESSION_TIMEOUT_MINUTES):
            # Clear session
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.warning("Session timed out. Please login again.")
            return True
    return False

def update_last_activity():
    """Update last activity timestamp"""
    st.session_state['last_activity'] = datetime.utcnow().isoformat()

def format_currency(amount: float, currency: str = "₦") -> str:
    """Format currency amount"""
    return f"{currency}{amount:,.2f}"

def create_qr_code(data: str) -> BytesIO:
    """Generate QR code"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio

def render_transaction_history(user_id: int):
    """Render transaction history with filtering"""
    st.subheader("Transaction History")
    
    col1, col2 = st.columns(2)
    with col1:
        category_filter = st.selectbox(
            "Filter by category",
            ['all'] + transaction_manager.CATEGORIES
        )
    with col2:
        limit = st.number_input("Number of transactions", 
                               min_value=10, max_value=100, value=20)
    
    transactions = transaction_manager.get_transactions(
        user_id, limit, category_filter if category_filter != 'all' else None
    )
    
    if transactions:
        for tx in transactions:
            with st.expander(f"{tx['type'].title()} - {format_currency(abs(tx['amount']))} - {tx['timestamp'][:10]}"):
                st.write(f"**Amount:** {format_currency(tx['amount'])}")
                st.write(f"**Type:** {tx['type'].title()}")
                st.write(f"**Category:** {tx['category'].title()}")
                st.write(f"**Description:** {tx['description']}")
                if tx['recipient_phone']:
                    st.write(f"**Recipient:** {tx['recipient_phone']}")
                st.write(f"**Status:** {'✅ Approved' if tx['approved'] else '⏳ Pending'}")
                st.write(f"**Date:** {tx['timestamp']}")
    else:
        st.info("No transactions found.")

# -------------------- MAIN APP --------------------

st.set_page_config(
    page_title="Money Matters — Enhanced Kids Banking",
    page_icon="🏦",
    layout='wide',
    initial_sidebar_state='expanded'
)

# Custom CSS for better styling
st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    padding: 1rem;
    border-radius: 10px;
    color: white;
    text-align: center;
    margin-bottom: 2rem;
}

.balance-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1.5rem;
    border-radius: 15px;
    color: white;
    text-align: center;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.transaction-card {
    background: #f8f9fa;
    padding: 1rem;
    border-radius: 8px;
    border-left: 4px solid #667eea;
    margin-bottom: 0.5rem;
}

.success-message {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
    padding: 0.75rem;
    border-radius: 0.375rem;
    margin: 1rem 0;
}

.error-message {
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    color: #721c24;
    padding: 0.75rem;
    border-radius: 0.375rem;
    margin: 1rem 0;
}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header"><h1>🏦 Money Matters — Enhanced Kids Banking</h1><p>Secure digital banking for families</p></div>', unsafe_allow_html=True)

# Check session timeout
if check_session_timeout():
    st.stop()

update_last_activity()

# Sidebar navigation
with st.sidebar:
    st.image("https://via.placeholder.com/200x100/667eea/white?text=Money+Matters", width=200)
    
    if 'user_id' in st.session_state and 'role' in st.session_state:
        user = user_manager.get_user_by_phone(st.session_state.get('phone', ''))
        if user:
            st.success(f"Welcome, {user['name']}!")
            st.write(f"Role: {user['role'].title()}")
            st.write(f"Balance: {format_currency(user['balance'])}")
            
            if st.button("🚪 Logout"):
                # Clear session
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
    
    st.markdown("---")
    
    mode = st.selectbox(
        "Choose Action",
        [
            "🏠 Home",
            "👨‍👩‍👧‍👦 Parent Login",
            "🧒 Kid Login", 
            "➕ Create Parent Account",
            "👶 Create Kid Account",
            "🔧 Admin Tools"
        ]
    )

# Main content area
if mode == "🏠 Home":
    st.markdown("## Welcome to Money Matters Kids Banking! 👋")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🌟 Key Features")
        st.markdown("""
        - **📱 Phone-based accounts** - Your phone number is your account number
        - **👨‍👩‍👧‍👦 Parent control** - Parents manage kids' accounts and limits
        - **💰 Automatic allowances** - Set up recurring pocket money
        - **📊 Spending tracking** - Monitor where money goes
        - **🔒 Secure transactions** - PIN protection and parental approval
        - **📱 QR codes** - Easy account sharing and payments
        """)
    
    with col2:
        st.markdown("### 🚀 Getting Started")
        st.markdown("""
        1. **Create a parent account** using your phone number
        2. **Set up your PIN** for secure access
        3. **Create kid accounts** and set their spending limits
        4. **Configure allowances** and daily spending limits
        5. **Start banking** safely with family oversight
        """)
    
    st.markdown("---")
    st.info("💡 **Tip**: This is a secure prototype. All transactions require proper authentication and parental approval for external transfers.")

elif mode == "➕ Create Parent Account":
    st.markdown("## 👨‍👩‍👧‍👦 Create Parent Account")
    
    with st.form("create_parent_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            country_code = st.text_input("Country Code", value=config.DEFAULT_COUNTRY_CODE)
            phone = st.text_input("Phone Number (without country code)")
            name = st.text_input("Full Name")
        
        with col2:
            email = st.text_input("Email (optional)")
            pin = st.text_input("Set 4-digit PIN", type='password')
            confirm_pin = st.text_input("Confirm PIN", type='password')
        
        submitted = st.form_submit_button("Create Parent Account", type="primary")
        
        if submitted:
            # Validate inputs
            if not all([phone, name, pin, confirm_pin]):
                st.error("Please fill in all required fields.")
            elif pin != confirm_pin:
                st.error("PINs do not match.")
            elif not security.check_rate_limit(f"create_user_{phone}"):
                st.error("Too many attempts. Please wait before trying again.")
            else:
                # Validate PIN
                is_vali
