from fastapi import FastAPI, HTTPException
from typing import List, Optional
import sqlite3
import hashlib
import time

app = FastAPI()

def create_connection():
    conn = sqlite3.connect('shopping_mall.db')
    return conn

def create_tables(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            full_name TEXT,
            address TEXT,
            payment_info TEXT,
            login_attempts INTEGER DEFAULT 0,  -- login_attempts 컬럼 추가
            locked_until INTEGER DEFAULT 0    -- locked_until 컬럼 추가
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            category TEXT,
            price REAL,
            thumbnail_url TEXT
        )
    ''')
    conn.commit()

salt = "saltsaltsalt"
LOGIN_ATTEMPT_LIMIT = 10
LOCK_TIME = 600 # lock 시간 

def add_user(conn, username, password, role, full_name, address, payment_info):
    hashed_password = hashlib.sha256((password + salt).encode()).hexdigest()
    cursor = conn.cursor()
    cursor.execute(f'INSERT INTO users (username, password, role, full_name, address, payment_info, login_attempts, locked_until) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (username, hashed_password, role, full_name, address, payment_info, 0, 0))  # login_attempts, locked_until 값 추가
    conn.commit()
    user = {"username": username, "password": hashed_password, "role": role, "full_name": full_name, "address": address, "payment_info": payment_info}
    return {"message": "User created successfully!", "user": user}

def register_admin(conn, username, password, full_name):
    cursor = conn.cursor()
    password = hashlib.sha256((password + salt).encode()).hexdigest()
    cursor.execute('INSERT INTO users (username, password, role, full_name, login_attempts, locked_until) VALUES (?, ?, ?, ?, ?, ?)',
                   (username, password, 'admin', full_name, 0, 0)) # login_attempts, locked_until 값 추가
    conn.commit()
    user = {"username": username, "password": password, "role": 'admin', "full_name": full_name}
    return {"message": "Admin registered successfully!", "user": user}

def authenticate_user(conn, username, password):
    hashed_password = hashlib.sha256((password + salt).encode()).hexdigest()  # 솔트, 해쉬 적용
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, hashed_password)) # SQLI 공격을 방지하기 위해 파라미터 수정(캠슐화)
    user = cursor.fetchone()
    if user:
        if user[8] > time.time():
            raise HTTPException(status_code=401, detail="Account is locked. Please try again later.")

        if user[7] >= LOGIN_ATTEMPT_LIMIT:
            # 계정 잠구기
            cursor.execute('UPDATE users SET locked_until = ?, login_attempts = 0 WHERE username = ?', (time.time() + LOCK_TIME, username))
            conn.commit()
            raise HTTPException(status_code=401, detail="Too many login attempts. Account is locked.")

        if user[2] == hashed_password:
            # 해쉬된 비번이면
            cursor.execute('UPDATE users SET login_attempts = 0 WHERE username = ?', (username,))
            conn.commit()
            user_info = {"username": user[1], "password": user[2], "role": user[3], "full_name": user[4], 
                        "address": user[5], "payment_info": user[6]}
            return {"message": f"Welcome back, {username}!", "user": user_info}
        else :
            cursor.execute('UPDATE users SET login_attempts = login_attempts + 1 WHERE username = ?', (username,))
            conn.commit()
            raise HTTPException(status_code=401, detail="Invalid username or password")
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

def get_all_products(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()
    return [{"name": product[1], "category": product[2], "price": product[3], "thumbnail_url": product[4]} for product in products]

def add_product(conn, name, category, price, thumbnail_url):
    cursor = conn.cursor()
    cursor.execute('INSERT INTO products (name, category, price, thumbnail_url) VALUES (?, ?, ?, ?)', (name, category, price, thumbnail_url))
    conn.commit()
    return {"message": "Product added successfully!"}

def update_user_info(conn, username, full_name, address, payment_info):
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET full_name = ?, address = ?, payment_info = ? WHERE username = ?', (full_name, address, payment_info, username))
    conn.commit()
    return {"message": "User information updated successfully!"}

def get_user_by_username(conn, username):
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    return cursor.fetchone()

@app.on_event("startup")
async def startup_event():
    conn = create_connection()
    create_tables(conn)
    if not get_user_by_username(conn, "admin"):
        register_admin(conn, "admin", "admin", "Admin User")  # 불필요한 인자 제거
    conn.close()

@app.get("/register")
async def register_user(username: str, password: str, role: str, full_name: str, address: Optional[str] = None, payment_info: Optional[str] = None):
    conn = create_connection()
    result = add_user(conn, username, password, role, full_name, address, payment_info)
    conn.close()
    return result

@app.get("/login")
async def login(username: str, password: str):
    conn = create_connection()
    result = authenticate_user(conn, username, password)
    conn.close()
    return result

@app.get("/products", response_model=List[dict])
async def get_products():
    conn = create_connection()
    products = get_all_products(conn)
    conn.close()
    return products

@app.get("/add_product")
async def add_new_product(name: str, category: str, price: float, thumbnail_url: str):
    conn = create_connection()
    result = add_product(conn, name, category, price, thumbnail_url)
    conn.close()
    return result

@app.get("/update_user_info")
async def update_user_info_endpoint(username: str, full_name: str, address: str, payment_info: str):
    conn = create_connection()
    result = update_user_info(conn, username, full_name, address, payment_info)
    conn.close()
    return result
