# database.py

import sqlite3
import os
from datetime import datetime

# Database file path
DB_PATH = "penny.db"

def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create categories table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        user_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')

    # Create expenses table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL NOT NULL,
        category_id INTEGER,
        description TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        payment_method TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
    ''')

    # Create budgets table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category_id INTEGER,
        amount REAL NOT NULL,
        period TEXT,
        start_date DATE,
        end_date DATE,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
    ''')

    conn.commit()
    conn.close()

def add_user(user_id: int, username: str = None):
    """Add a new user to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    
    conn.commit()
    conn.close()

def add_expense(user_id: int, amount: float, category: str, description: str = None, payment_method: str = None):
    """Add a new expense to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get or create category
    cursor.execute(
        "SELECT id FROM categories WHERE name = ? AND user_id = ?",
        (category, user_id)
    )
    category_id = cursor.fetchone()
    
    if not category_id:
        cursor.execute(
            "INSERT INTO categories (name, user_id) VALUES (?, ?)",
            (category, user_id)
        )
        category_id = cursor.lastrowid
    else:
        category_id = category_id[0]
    
    # Add expense
    cursor.execute(
        """
        INSERT INTO expenses (user_id, amount, category_id, description, payment_method)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, amount, category_id, description, payment_method)
    )
    
    conn.commit()
    conn.close()

def get_user_expenses(user_id: int, limit: int = 10):
    """Get recent expenses for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT e.amount, c.name, e.description, e.date, e.payment_method
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ?
        ORDER BY e.date DESC
        LIMIT ?
        """,
        (user_id, limit)
    )
    
    expenses = cursor.fetchall()
    conn.close()
    return expenses

def get_user_categories(user_id: int):
    """Get all categories for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT name FROM categories WHERE user_id = ?",
        (user_id,)
    )
    
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return categories

# Initialize database when module is imported
if not os.path.exists(DB_PATH):
    init_db() 