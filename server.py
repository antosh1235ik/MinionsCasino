import os
import sqlite3
import urllib.request
import json
from datetime import date
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

DB_NAME = "casino.db"
TARGET_GIFTS_USER = "8133727762"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 1000,
                ton_balance REAL DEFAULT 0.0,
                free_spins INTEGER DEFAULT 5,
                referral_code TEXT,
                referral_earnings INTEGER DEFAULT 0,
                last_daily TEXT,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                total_wagered INTEGER DEFAULT 0,
                total_won INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gifts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                image TEXT NOT NULL,
                rarity TEXT NOT NULL,
                price INTEGER DEFAULT 50,
                owner_id TEXT NOT NULL,
                original_holder TEXT NOT NULL,
                is_for_sale INTEGER DEFAULT 1
            )
        ''')
        conn.commit()
        ensure_user(cursor, TARGET_GIFTS_USER)
        sync_target_user_gifts(cursor)

def ensure_user(cursor, user_id):
    cursor.execute("SELECT * FROM users WHERE id = ?", (str(user_id),))
    user = cursor.fetchone()
    if not user:
        ref_code = f"REF{str(user_id)[-4:]}"
        cursor.execute("INSERT INTO users (id, referral_code, balance) VALUES (?, ?, 1000)", (str(user_id), ref_code))
        cursor.execute("SELECT * FROM users WHERE id = ?", (str(user_id),))
        user = cursor.fetchone()
    return user

def sync_target_user_gifts(cursor):
    """Синхронизация Telegram подарков пользователя 8133727762"""
    cursor.execute("SELECT COUNT(*) FROM gifts WHERE original_holder = ?", (TARGET_GIFTS_USER,))
    count = cursor.fetchone()[0]
    
    # Дефолтные подарки профиля 8133727762 из базы Telegram Gifts
    default_gifts = [
        ("gift_tg_8133_1", "Delicious Cake #4921", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC8xL1RhMW81OG9yOW9NLnBuZw.png", "Limited Gift", 150, TARGET_GIFTS_USER, TARGET_GIFTS_USER, 1),
        ("gift_tg_8133_2", "Green Star #182", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC8yL1RhMW81OG9yOW9NLnBuZw.png", "Rare Gift", 300, TARGET_GIFTS_USER, TARGET_GIFTS_USER, 1),
        ("gift_tg_8133_3", "Plush Pepe #88", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC8zL1RhMW81OG9yOW9NLnBuZw.png", "Legendary Gift", 750, TARGET_GIFTS_USER, TARGET_GIFTS_USER, 1),
        ("gift_tg_8133_4", "Party Sparkler #901", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC80L1RhMW81OG9yOW9NLnBuZw.png", "Special Gift", 99, TARGET_GIFTS_USER, TARGET_GIFTS_USER, 1)
    ]
    
    if count == 0:
        cursor.executemany('''
            INSERT OR IGNORE INTO gifts (id, name, image, rarity, price, owner_id, original_holder, is_for_sale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', default_gifts)

init_db()

@app.route('/')
def index():
    for f in ['index.html', '67.html']:
        if os.path.exists(f):
            return send_file(f)
    return "<h1>Casino API</h1><p>index.html не найден</p>"

# Данные пользователя
@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, str(user_id))
        return jsonify({
            "id": user["id"],
            "balance": user["balance"],
            "ton_balance": user["ton_balance"],
            "free_spins": user["free_spins"],
            "referral_code": user["referral_code"]
        })

# Депозит с комиссией 1%
@app.route('/api/balance/add', methods=['POST'])
def add_balance():
    data = request.get_json(silent=True) or {}
    user_id = str(request.args.get('user_id') or data.get('user_id') or '')
    amount = float(request.args.get('amount') or data.get('amount') or 0)
    currency = str(request.args.get('currency') or data.get('currency') or 'stars').lower()

    if not user_id or amount <= 0:
        return jsonify({"detail": "Некорректные параметры"}), 400

    net = amount * 0.99

    with get_db() as conn:
        cursor = conn.cursor()
        ensure_user(cursor, user_id)
        if currency == 'ton':
            cursor.execute("UPDATE users SET ton_balance = ton_balance + ? WHERE id = ?", (net, user_id))
        else:
            net_int = int(net)
            cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (net_int, user_id))
        conn.commit()

        cursor.execute("SELECT balance, ton_balance FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return jsonify({"status": "ok", "new_balance": row["balance"], "new_ton_balance": row["ton_balance"]})

# Маркет: только актуальные выставленные подарки пользователя 8133727762
@app.route('/api/market', methods=['GET'])
def get_market():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM gifts 
            WHERE owner_id = ? AND is_for_sale = 1
        ''', (TARGET_GIFTS_USER,))
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows])

# Подарки текущего пользователя (в профиль и инвентарь)
@app.route('/api/nfts/<user_id>', methods=['GET'])
def get_my_gifts(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gifts WHERE owner_id = ?", (str(user_id),))
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows])

# Настоящая покупка подарка
@app.route('/api/nfts/buy', methods=['POST'])
def buy_gift():
    data = request.get_json(silent=True) or {}
    user_id = str(request.args.get('user_id') or data.get('user_id') or '')
    gift_id = str(request.args.get('nft_id') or data.get('nft_id') or '')

    with get_db() as conn:
        cursor = conn.cursor()
        buyer = ensure_user(cursor, user_id)

        cursor.execute("SELECT * FROM gifts WHERE id = ?", (gift_id,))
        gift = cursor.fetchone()

        if not gift:
            return jsonify({"detail": "Подарок не найден"}), 404
        if gift["is_for_sale"] != 1:
            return jsonify({"detail": "Подарок уже куплен другим игроком"}), 400
        if str(gift["owner_id"]) == user_id:
            return jsonify({"detail": "Вы уже владеете этим подарком"}), 400
        if buyer["balance"] < gift["price"]:
            return jsonify({"detail": f"Не хватает Stars! Нужно ⭐ {gift['price']}"}), 400

        price = gift["price"]
        seller_id = str(gift["owner_id"])

        # Списание со счета покупателя, начисление владельцу 8133727762 и передача владения
        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, seller_id))
        cursor.execute("UPDATE gifts SET owner_id = ?, is_for_sale = 0 WHERE id = ?", (user_id, gift_id))
        conn.commit()

        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        return jsonify({
            "status": "ok",
            "message": f"Подарок «{gift['name']}» успешно куплен!",
            "new_balance": cursor.fetchone()["balance"]
        })

# Перепродажа своего подарка
@app.route('/api/nfts/sell', methods=['POST'])
def sell_gift():
    data = request.get_json(silent=True) or {}
    user_id = str(request.args.get('user_id') or data.get('user_id') or '')
    gift_id = str(request.args.get('nft_id') or data.get('nft_id') or '')
    price = int(request.args.get('price') or data.get('price') or 100)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gifts WHERE id = ? AND owner_id = ?", (gift_id, user_id))
        if not cursor.fetchone():
            return jsonify({"detail": "Подарок не найден в вашем инвентаре"}), 404
        cursor.execute("UPDATE gifts SET is_for_sale = 1, price = ? WHERE id = ?", (price, gift_id))
        conn.commit()
        return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
