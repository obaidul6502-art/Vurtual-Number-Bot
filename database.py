import sqlite3
import psycopg2
from config import DATABASE_URL

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        return sqlite3.connect('bot_database.db')

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock (
                id SERIAL PRIMARY KEY, item_type TEXT, item_data TEXT, price REAL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id SERIAL PRIMARY KEY, user_id BIGINT, platform TEXT, item_data TEXT, price REAL, purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    else:
        # SQLite-এ একাধিক কমান্ড চালানোর জন্য executescript ব্যবহার করতে হয়
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT, item_type TEXT, item_data TEXT, price REAL
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, platform TEXT, item_data TEXT, price REAL, purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
    conn.commit()
    cursor.close()
    conn.close()

def get_user(user_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(f"SELECT balance FROM users WHERE user_id = {ph}", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute(f"INSERT INTO users (user_id, username, balance) VALUES ({ph}, {ph}, 0.0)", (user_id, username))
        conn.commit()
        balance = 0.0
    else:
        balance = row[0]
    cursor.close()
    conn.close()
    return balance

def update_balance(user_id, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(f"UPDATE users SET balance = balance + {ph} WHERE user_id = {ph}", (amount, user_id))
    conn.commit()
    cursor.close()
    conn.close()

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return [u[0] for u in users]

def get_stock_info(item_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(f"SELECT COUNT(*), AVG(price) FROM stock WHERE item_type = {ph}", (item_type,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    count = row[0] if row else 0
    price = row[1] if row and row[1] is not None else 0.0
    return count, price

def get_total_users_balance():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(balance) FROM users")
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return float(row[0]) if row and row[0] is not None else 0.0