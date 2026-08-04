import hashlib
from tinydb import TinyDB, Query

# Initialize NoSQL Database file (JSON Document Store)
db = TinyDB('database.json')
users_table = db.table('users')

def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

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

# Ensure database is initialized on import
init_db()
