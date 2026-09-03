import os
import sqlite3
import time
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

DB_NAME = "casino.db"
BOT_TOKEN = "8909097529:AAHrqlwMZI1AD9XYcS3nFeEOksA07eEqJPU"
CASINO_TON_WALLET = "UQDfH8vUHmcSKI0c3qWxv7e2eH9ZB9Q8WW2SaqnjDaRjm1Lp"
TARGET_SELLER_ID = "8133727762"

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
                balance INTEGER DEFAULT 0,
                ton_balance REAL DEFAULT 0.0,
                free_spins INTEGER DEFAULT 0,
                referral_code TEXT,
                referral_earnings INTEGER DEFAULT 0,
                last_daily TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nfts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                image TEXT NOT NULL,
                rarity TEXT NOT NULL,
                price INTEGER DEFAULT 50,
                owner_id TEXT NOT NULL,
                is_for_sale INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_payments (
                payment_id TEXT PRIMARY KEY,
                user_id TEXT,
                amount REAL,
                currency TEXT,
                created_at INTEGER
            )
        ''')
        conn.commit()

        ensure_user(cursor, TARGET_SELLER_ID)
        cursor.execute("SELECT COUNT(*) FROM nfts WHERE owner_id = ?", (TARGET_SELLER_ID,))
        if cursor.fetchone()[0] == 0:
            sample_gifts = [
                ("gift_cake_4921", "Delicious Cake #4921", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC8xL1RhMW81OG9yOW9NLnBuZw.png", "Limited Gift", 100, TARGET_SELLER_ID, 1),
                ("gift_star_182", "Green Star #182", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC8yL1RhMW81OG9yOW9NLnBuZw.png", "Rare Gift", 250, TARGET_SELLER_ID, 1),
                ("gift_pepe_88", "Plush Pepe #88", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC8zL1RhMW81OG9yOW9NLnBuZw.png", "Legendary Gift", 500, TARGET_SELLER_ID, 1),
                ("gift_spark_901", "Party Sparkler #901", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC80L1RhMW81OG9yOW9NLnBuZw.png", "Special Gift", 80, TARGET_SELLER_ID, 1)
            ]
            cursor.executemany('''
                INSERT INTO nfts (id, name, image, rarity, price, owner_id, is_for_sale)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', sample_gifts)
            conn.commit()

def ensure_user(cursor, user_id):
    cursor.execute("SELECT * FROM users WHERE id = ?", (str(user_id),))
    user = cursor.fetchone()
    if not user:
        ref_code = f"REF{str(user_id)[-4:]}"
        cursor.execute("INSERT INTO users (id, referral_code, balance) VALUES (?, ?, 0)", (str(user_id), ref_code))
        cursor.execute("SELECT * FROM users WHERE id = ?", (str(user_id),))
        user = cursor.fetchone()
    return user

init_db()

@app.route('/')
def index():
    for f in ['index.html', '67.html']:
        if os.path.exists(f):
            return send_file(f)
    return "<h1>Casino API Running</h1>"

# 1. СОЗДАНИЕ ИНВОЙСА TELEGRAM STARS
@app.route('/api/stars/create-invoice', methods=['POST'])
def create_stars_invoice():
    data = request.json or {}
    user_id = str(data.get('user_id', ''))
    raw_amount = int(data.get('amount', 100))

    if not user_id or raw_amount <= 0:
        return jsonify({"detail": "Некорректная сумма или ID"}), 400

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink"
    payload = {
        "title": "Пополнение баланса Stars",
        "description": f"Пополнение на {raw_amount} звёзд. Получите: {int(raw_amount * 0.99)} ⭐ (Комиссия 1%)",
        "payload": f"stars_dep_{user_id}_{raw_amount}_{int(time.time())}",
        "currency": "XTR",
        "prices": [{"label": "Telegram Stars", "amount": raw_amount}]
    }

    try:
        res = requests.post(url, json=payload, timeout=10).json()
        if not res.get("ok"):
            return jsonify({"detail": res.get("description", "Ошибка Bot API")}), 400
        return jsonify({"invoice_link": res["result"]})
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

# ВЕБХУК ДЛЯ ПОДТВЕРЖДЕНИЯ ОПЛАТЫ STARS
@app.route('/api/telegram-webhook', methods=['POST'])
def telegram_webhook():
    update = request.json or {}

    if "pre_checkout_query" in update:
        query_id = update["pre_checkout_query"]["id"]
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerPreCheckoutQuery", json={
            "pre_checkout_query_id": query_id,
            "ok": True
        })
        return jsonify({"ok": True})

    msg = update.get("message", {})
    payment = msg.get("successful_payment")
    if payment and payment.get("currency") == "XTR":
        total_amount = payment.get("total_amount", 0)
        pay_payload = payment.get("invoice_payload", "")
        parts = pay_payload.split("_")
        if len(parts) >= 4:
            user_id = parts[2]
            net_stars = int(total_amount * 0.99)

            with get_db() as conn:
                cursor = conn.cursor()
                charge_id = payment.get("telegram_payment_charge_id")
                cursor.execute("SELECT payment_id FROM processed_payments WHERE payment_id = ?", (charge_id,))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO processed_payments VALUES (?, ?, ?, ?, ?)",
                                   (charge_id, user_id, net_stars, "STARS", int(time.time())))
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (net_stars, user_id))
                    conn.commit()
    return jsonify({"ok": True})

# 2. ПРОВЕРКА РЕАЛЬНОГО ДЕПОЗИТА TON В БЛОКЧЕЙНЕ
@app.route('/api/ton/verify-deposit', methods=['POST'])
def verify_ton_deposit():
    data = request.json or {}
    user_id = str(data.get('user_id', ''))
    comment = str(data.get('comment', ''))
    expected_amount = float(data.get('amount', 0))

    if not user_id or not comment or expected_amount <= 0:
        return jsonify({"detail": "Некорректные параметры"}), 400

    # Проверка через TonAPI
    url = f"https://tonapi.io/v2/blockchain/accounts/{CASINO_TON_WALLET}/transactions?limit=25"
    try:
        res = requests.get(url, timeout=10).json()
        txs = res.get("transactions", [])

        for tx in txs:
            in_msg = tx.get("in_msg", {})
            msg_comment = in_msg.get("decoded_body", {}).get("text", "")
            raw_val = int(in_msg.get("value", 0)) / 1e9

            if msg_comment == comment and raw_val >= (expected_amount * 0.99):
                tx_hash = tx.get("hash")
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT payment_id FROM processed_payments WHERE payment_id = ?", (tx_hash,))
                    if cursor.fetchone():
                        return jsonify({"detail": "Транзакция уже зачислена"}), 400

                    net_ton = round(raw_val * 0.99, 4)
                    cursor.execute("INSERT INTO processed_payments VALUES (?, ?, ?, ?, ?)",
                                   (tx_hash, user_id, net_ton, "TON", int(time.time())))
                    cursor.execute("UPDATE users SET ton_balance = ton_balance + ? WHERE id = ?", (net_ton, user_id))
                    conn.commit()
                    return jsonify({"status": "ok", "credited": net_ton})

        return jsonify({"detail": "Транзакция ещё обрабатывается блокчейном"}), 404
    except Exception as e:
        return jsonify({"detail": f"Ошибка связи с блокчейном: {str(e)}"}), 500

# ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ
@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, str(user_id))
        return jsonify(dict(user))

# МАРКЕТ: ТОЛЬКО ПОДАРКИ 8133727762
@app.route('/api/market', methods=['GET'])
def get_market():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfts WHERE owner_id = ? AND is_for_sale = 1", (TARGET_SELLER_ID,))
        return jsonify([dict(r) for r in cursor.fetchall()])

# МОИ ПОДАРКИ (ИНВЕНТАРЬ И ПРОФИЛЬ)
@app.route('/api/nfts/<user_id>', methods=['GET'])
def get_user_nfts(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfts WHERE owner_id = ?", (str(user_id),))
        return jsonify([dict(r) for r in cursor.fetchall()])

# ПОКУПКА ПОДАРКА
@app.route('/api/nfts/buy', methods=['POST'])
def buy_nft():
    data = request.json or {}
    user_id = str(data.get('user_id', ''))
    nft_id = str(data.get('nft_id', ''))

    with get_db() as conn:
        cursor = conn.cursor()
        buyer = ensure_user(cursor, user_id)
        cursor.execute("SELECT * FROM nfts WHERE id = ? AND is_for_sale = 1", (nft_id,))
        nft = cursor.fetchone()

        if not nft:
            return jsonify({"detail": "Предмет уже куплен"}), 404
        if buyer["balance"] < nft["price"]:
            return jsonify({"detail": f"Не хватает Stars. Баланс: {buyer['balance']} ⭐, цена: {nft['price']} ⭐"}), 400

        price = nft["price"]
        seller_id = str(nft["owner_id"])

        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, seller_id))
        cursor.execute("UPDATE nfts SET owner_id = ?, is_for_sale = 0 WHERE id = ?", (user_id, nft_id))
        conn.commit()

        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        return jsonify({"status": "ok", "new_balance": cursor.fetchone()["balance"]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
