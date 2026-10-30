import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preco_certo.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tracked items / searches
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tracked_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        target_price REAL,
        user_intent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_checked TIMESTAMP,
        status TEXT DEFAULT 'active'
    )
    """)
    
    # Price snapshots for historical charts
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        title TEXT NOT NULL,
        price REAL NOT NULL,
        original_price REAL,
        source TEXT NOT NULL,
        url TEXT,
        rating REAL,
        reviews_count INTEGER,
        free_shipping INTEGER DEFAULT 0,
        captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES tracked_products(id)
    )
    """)
    
    # AI Decision Recommendations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        verdict TEXT NOT NULL,
        best_pick_title TEXT,
        best_pick_price REAL,
        summary TEXT NOT NULL,
        pros_cons_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES tracked_products(id)
    )
    """)
    
    conn.commit()
    conn.close()

def save_tracked_product(name: str, target_price: Optional[float] = None, user_intent: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tracked_products (name, target_price, user_intent) VALUES (?, ?, ?)",
        (name, target_price, user_intent)
    )
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id

def save_price_records(records: List[Dict[str, Any]], product_id: Optional[int] = None):
    conn = get_connection()
    cursor = conn.cursor()
    for r in records:
        cursor.execute("""
        INSERT INTO price_history (
            product_id, title, price, original_price, source, url, rating, reviews_count, free_shipping
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            r.get("title", ""),
            float(r.get("price", 0.0)),
            float(r.get("original_price")) if r.get("original_price") else None,
            r.get("source", "Mercado Livre"),
            r.get("url", ""),
            float(r.get("rating", 0.0)),
            int(r.get("reviews_count", 0)),
            1 if r.get("free_shipping") else 0
        ))
    if product_id:
        cursor.execute("UPDATE tracked_products SET last_checked = CURRENT_TIMESTAMP WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def save_ai_recommendation(product_id: int, verdict: str, best_pick: Dict[str, Any], summary: str, pros_cons_json: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO ai_recommendations (product_id, verdict, best_pick_title, best_pick_price, summary, pros_cons_json)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        product_id,
        verdict,
        best_pick.get("title", ""),
        float(best_pick.get("price", 0.0)),
        summary,
        pros_cons_json
    ))
    conn.commit()
    conn.close()

def get_tracked_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, 
               (SELECT MIN(price) FROM price_history WHERE product_id = p.id) as lowest_price,
               (SELECT AVG(price) FROM price_history WHERE product_id = p.id) as avg_price,
               (SELECT COUNT(*) FROM price_history WHERE product_id = p.id) as offers_count
        FROM tracked_products p
        ORDER BY p.id DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_product_details(product_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tracked_products WHERE id = ?", (product_id,))
    product = dict(cursor.fetchone() or {})
    
    cursor.execute("SELECT * FROM price_history WHERE product_id = ? ORDER BY price ASC", (product_id,))
    offers = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM ai_recommendations WHERE product_id = ? ORDER BY id DESC LIMIT 1", (product_id,))
    rec_row = cursor.fetchone()
    recommendation = dict(rec_row) if rec_row else None
    
    conn.close()
    return {"product": product, "offers": offers, "recommendation": recommendation}
