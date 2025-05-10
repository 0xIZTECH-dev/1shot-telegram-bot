# database.py

import sqlite3
import os
from datetime import datetime

# Database file path
DB_PATH = "penny.db"

def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Drop existing tables if they exist
    cursor.execute("DROP TABLE IF EXISTS expenses")
    cursor.execute("DROP TABLE IF EXISTS budgets")
    cursor.execute("DROP TABLE IF EXISTS goals")
    cursor.execute("DROP TABLE IF EXISTS users")
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create expenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            category TEXT,
            description TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            payment_method TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create budgets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            amount REAL,
            period TEXT,
            start_date TEXT,
            end_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create goals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL DEFAULT 0,
            deadline TEXT,
            category TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def add_user(user_id: int, username: str = None):
    """Add a new user to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)",
        (user_id, username)
    )
    
    conn.commit()
    conn.close()

def add_expense(user_id: int, amount: float, category: str, description: str = None, payment_method: str = None):
    """Add a new expense to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO expenses (user_id, amount, category, description, payment_method)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, amount, category, description, payment_method)
    )
    
    conn.commit()
    conn.close()

def get_user_expenses(user_id: int, limit: int = 10):
    """Get recent expenses for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT amount, category, description, date, payment_method
        FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC
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

def add_goal(user_id: int, name: str, target_amount: float, deadline: str = None, category: str = None):
    """Add a new financial goal."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO goals (user_id, name, target_amount, deadline, category)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, name, target_amount, deadline, category)
    )
    
    conn.commit()
    conn.close()

def get_user_goals(user_id: int, status: str = 'active'):
    """Get all goals for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT id, name, target_amount, current_amount, deadline, category, status
        FROM goals
        WHERE user_id = ? AND status = ?
        ORDER BY deadline ASC
        """,
        (user_id, status)
    )
    
    goals = cursor.fetchall()
    conn.close()
    return goals

def update_goal_progress(goal_id: int, amount: float):
    """Update the progress of a goal."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        UPDATE goals
        SET current_amount = current_amount + ?
        WHERE id = ?
        """,
        (amount, goal_id)
    )
    
    conn.commit()
    conn.close()

def complete_goal(goal_id: int):
    """Mark a goal as completed."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE goals SET status = 'completed' WHERE id = ?",
        (goal_id,)
    )
    
    conn.commit()
    conn.close()

def delete_goal(goal_id: int):
    """Delete a goal."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    
    conn.commit()
    conn.close()

def add_budget(user_id: int, category: str, amount: float, period: str, start_date: str, end_date: str):
    """Add a new budget."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO budgets (user_id, category, amount, period, start_date, end_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, category, amount, period, start_date, end_date)
    )
    
    conn.commit()
    conn.close()

def get_user_budgets(user_id: int):
    """Get all budgets for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT id, category, amount, period, start_date, end_date
        FROM budgets
        WHERE user_id = ? AND end_date >= date('now')
        ORDER BY start_date DESC
        """,
        (user_id,)
    )
    
    budgets = cursor.fetchall()
    conn.close()
    return budgets

def update_budget(budget_id: int, amount: float):
    """Update a budget's amount."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE budgets SET amount = ? WHERE id = ?",
        (amount, budget_id)
    )
    
    conn.commit()
    conn.close()

def delete_budget(budget_id: int):
    """Delete a budget."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
    
    conn.commit()
    conn.close()

def get_budget_progress(user_id: int, category: str = None):
    """Get budget progress for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if category:
        # Get budget and expenses for specific category
        cursor.execute(
            """
            SELECT b.amount, b.period, b.start_date, b.end_date,
                   COALESCE(SUM(e.amount), 0) as spent
            FROM budgets b
            LEFT JOIN expenses e ON e.user_id = b.user_id 
                AND e.category = b.category
                AND e.date BETWEEN b.start_date AND b.end_date
            WHERE b.user_id = ? AND b.category = ?
            GROUP BY b.id
            """,
            (user_id, category)
        )
    else:
        # Get total budget and expenses
        cursor.execute(
            """
            SELECT SUM(b.amount) as total_budget,
                   COALESCE(SUM(e.amount), 0) as total_spent
            FROM budgets b
            LEFT JOIN expenses e ON e.user_id = b.user_id 
                AND e.date BETWEEN b.start_date AND b.end_date
            WHERE b.user_id = ?
            """,
            (user_id,)
        )
    
    result = cursor.fetchone()
    conn.close()
    return result

# Initialize database when module is imported
init_db()  # Always run init_db to ensure tables exist 