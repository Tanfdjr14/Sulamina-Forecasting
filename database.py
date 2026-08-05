import hashlib
import re
import datetime
from tinydb import TinyDB, Query

# Initialize NoSQL Database file (JSON Document Store)
db = TinyDB('database.json')
users_table = db.table('users')

def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def is_valid_google_email(email: str) -> tuple[bool, str]:
    """Validate if the email is a legitimate Google Account format (@gmail.com or @googlemail.com)."""
    email = email.strip().lower()
    # Google email rules: 6-30 chars, alphanumeric with dots, ending with @gmail.com or @googlemail.com
    pattern = r'^[a-z0-9](\.?[a-z0-9]){5,29}@(gmail|googlemail)\.com$'
    
    if not re.match(pattern, email):
        return False, "Email harus berupa Akun Google resmi (@gmail.com) dengan nama pengguna valid!"
    
    return True, "Email valid"

def init_db():
    """Seed initial user into NoSQL database if not exists."""
    User = Query()
    target_email = "snorkelzone@gmail.com"
    target_pass = "@test112233"
    
    existing = users_table.search(User.email == target_email)
    if not existing:
        users_table.insert({
            'email': target_email,
            'password': hash_password(target_pass),
            'role': 'admin',
            'created_at': '2024-01-01'
        })

def verify_user(email: str, password: str) -> bool:
    """Verify user credentials against NoSQL database."""
    init_db()
    User = Query()
    result = users_table.search((User.email == email.strip().lower()) & 
                               (User.password == hash_password(password)))
    return len(result) > 0

def register_user(email: str, password: str) -> tuple[bool, str]:
    """Register a new user account into the NoSQL database after strict Google email validation."""
    init_db()
    email = email.strip().lower()
    
    # 1. Check valid Google email domain and format
    is_valid, msg = is_valid_google_email(email)
    if not is_valid:
        return False, msg
        
    # 2. Check password length
    if len(password) < 6:
        return False, "Password minimal harus 6 karakter!"
        
    # 3. Check duplicate email in NoSQL DB
    User = Query()
    existing = users_table.search(User.email == email)
    if existing:
        return False, "Akun Google ini sudah terdaftar di database! Silakan pilih menu Login."
        
    # 4. Insert into NoSQL database
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    users_table.insert({
        'email': email,
        'password': hash_password(password),
        'role': 'user',
        'created_at': now_str
    })
    
    return True, "Pendaftaran berhasil! Akun Google Anda telah tersimpan di NoSQL Database. Silakan pindah ke tab Login."

# Ensure database is initialized on import
init_db()
