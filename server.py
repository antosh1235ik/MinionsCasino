import os
import random
import sqlite3
import time
import requests
from datetime import date
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
                last_daily TEXT,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                total_wagered INTEGER DEFAULT 0,
                total_won INTEGER DEFAULT 0
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
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id TEXT,
                referred_id TEXT PRIMARY KEY
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
    for f in ['67.html', 'index.html']:
        if os.path.exists(f):
            return send_file(f)
    return "<h1>Casino API Running</h1>"

# ===== 1. НАСТОЯЩИЙ ИНВОЙС TELEGRAM STARS =====
@app.route('/api/stars/create-invoice', methods=['POST'])
def create_stars_invoice():
    data = request.json or {}
    user_id = str(data.get('user_id', ''))
    raw_amount = int(data.get('amount', 100))

    if not user_id or raw_amount <= 0:
        return jsonify({"detail": "Некорректная сумма"}), 400

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink"
    payload = {
        "title": "Пополнение баланса Stars",
        "description": f"Пополнение на {raw_amount} звёзд. Зачислится: {int(raw_amount * 0.99)} ⭐ (Комиссия 1%)",
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

# ВЕБХУК: ЕДИНСТВЕННЫЙ СПОСОБ ЗАЧИСЛЕНИЯ STARS
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

# ===== 2. БЛОКЧЕЙН-ПРОВЕРКА TON (ЕДИНСТВЕННЫЙ СПОСОБ ЗАЧИСЛЕНИЯ TON) =====
@app.route('/api/ton/verify-deposit', methods=['POST'])
def verify_ton_deposit():
    data = request.json or {}
    user_id = str(data.get('user_id', ''))
    comment = str(data.get('comment', ''))
    expected_amount = float(data.get('amount', 0))

    if not user_id or not comment or expected_amount <= 0:
        return jsonify({"detail": "Некорректные параметры"}), 400

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

# ===== ПРОФИЛЬ, МАРКЕТ И ПОКУПКА =====
@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, str(user_id))
        cursor.execute("SELECT referred_id FROM referrals WHERE referrer_id = ?", (str(user_id),))
        refs = [r[0] for r in cursor.fetchall()]
        return jsonify({
            "id": user["id"],
            "balance": user["balance"],
            "ton_balance": user["ton_balance"],
            "free_spins": user["free_spins"],
            "referral_code": user["referral_code"],
            "referral_earnings": user["referral_earnings"],
            "referrals": refs,
            "last_daily": user["last_daily"]
        })

@app.route('/api/games/stats/<user_id>', methods=['GET'])
def get_stats(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, str(user_id))
        return jsonify({
            "level": user["level"],
            "xp": user["xp"],
            "total_wagered": user["total_wagered"],
            "total_won": user["total_won"],
            "free_spins": user["free_spins"]
        })

@app.route('/api/market', methods=['GET'])
def get_market():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfts WHERE owner_id = ? AND is_for_sale = 1", (TARGET_SELLER_ID,))
        return jsonify([dict(r) for r in cursor.fetchall()])

@app.route('/api/nfts/<user_id>', methods=['GET'])
def get_user_nfts(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfts WHERE owner_id = ?", (str(user_id),))
        return jsonify([dict(r) for r in cursor.fetchall()])

@app.route('/api/nfts/buy', methods=['POST'])
def buy_nft():
    data = request.get_json(silent=True) or {}
    user_id = str(request.args.get('user_id') or data.get('user_id') or '')
    nft_id = str(request.args.get('nft_id') or data.get('nft_id') or '')

    with get_db() as conn:
        cursor = conn.cursor()
        buyer = ensure_user(cursor, user_id)
        cursor.execute("SELECT * FROM nfts WHERE id = ? AND is_for_sale = 1", (nft_id,))
        nft = cursor.fetchone()

        if not nft:
            return jsonify({"detail": "Предмет не продается"}), 400
        if str(nft["owner_id"]) == user_id:
            return jsonify({"detail": "Вы уже владеете этим предметом"}), 400
        if buyer["balance"] < nft["price"]:
            return jsonify({"detail": "Недостаточно Stars на балансе"}), 400

        price = nft["price"]
        seller_id = str(nft["owner_id"])

        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, seller_id))
        cursor.execute("UPDATE nfts SET owner_id = ?, is_for_sale = 0 WHERE id = ?", (user_id, nft_id))
        conn.commit()

        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        return jsonify({"status": "ok", "new_balance": cursor.fetchone()["balance"]})

@app.route('/api/nfts/sell', methods=['POST'])
def sell_nft():
    data = request.get_json(silent=True) or {}
    user_id = str(request.args.get('user_id') or data.get('user_id') or '')
    nft_id = str(request.args.get('nft_id') or data.get('nft_id') or '')
    price = int(request.args.get('price') or data.get('price') or 50)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfts WHERE id = ? AND owner_id = ?", (nft_id, user_id))
        if not cursor.fetchone():
            return jsonify({"detail": "Предмет не найден"}), 404
        cursor.execute("UPDATE nfts SET is_for_sale = 1, price = ? WHERE id = ?", (price, nft_id))
        conn.commit()
        return jsonify({"status": "ok"})

@app.route('/api/nfts/transfer', methods=['POST'])
def transfer_nft():
    data = request.get_json(silent=True) or {}
    sender_id = str(request.args.get('sender_id') or data.get('sender_id') or '')
    receiver_id = str(request.args.get('receiver_id') or data.get('receiver_id') or '')
    nft_id = str(request.args.get('nft_id') or data.get('nft_id') or '')

    with get_db() as conn:
        cursor = conn.cursor()
        ensure_user(cursor, receiver_id)
        cursor.execute("SELECT * FROM nfts WHERE id = ? AND owner_id = ?", (nft_id, sender_id))
        if not cursor.fetchone():
            return jsonify({"detail": "Предмет не найден"}), 404
        cursor.execute("UPDATE nfts SET owner_id = ?, is_for_sale = 0 WHERE id = ?", (receiver_id, nft_id))
        conn.commit()
        return jsonify({"status": "ok"})

# ===== ИГРЫ КАЗИНО (ПРОВЕРКА БАЛАНСА НА СЕРВЕРЕ) =====
@app.route('/api/games/slots/spin', methods=['POST'])
def spin_slots():
    user_id = str(request.args.get('user_id'))
    bet = int(request.args.get('bet', 10))
    symbols = ['🍒', '🍋', '🍊', '🍇', '🔔', '💎', '⭐', '7️⃣']
    reels = [random.choice(symbols) for _ in range(9)]
    middle_row = [reels[1], reels[4], reels[7]]
    win = middle_row[0] == middle_row[1] == middle_row[2]
    win_amount = bet * 10 if win else 0

    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, user_id)
        if user["balance"] < bet:
            return jsonify({"detail": "Недостаточно средств"}), 400
        new_balance = user["balance"] - bet + win_amount
        cursor.execute("UPDATE users SET balance = ?, total_wagered = total_wagered + ?, total_won = total_won + ? WHERE id = ?", 
                       (new_balance, bet, win_amount, user_id))
        conn.commit()
        return jsonify({"reels": reels, "win": win, "win_amount": win_amount, "combo": middle_row, "new_balance": new_balance, "free_spins": 0})

@app.route('/api/games/roulette/spin', methods=['POST'])
def spin_roulette():
    user_id = str(request.args.get('user_id'))
    bet = int(request.args.get('bet', 10))
    bet_type = request.args.get('bet_type', 'red')
    number = random.randint(0, 36)
    red_numbers = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
    color = "green" if number == 0 else ("red" if number in red_numbers else "black")
    win = False
    payout = 2

    if bet_type == 'red' and color == 'red': win = True
    elif bet_type == 'black' and color == 'black': win = True
    elif bet_type == 'green' and color == 'green': win = True; payout = 36
    elif bet_type == 'even' and number > 0 and number % 2 == 0: win = True
    elif bet_type == 'odd' and number > 0 and number % 2 != 0: win = True

    win_amount = bet * payout if win else 0
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, user_id)
        if user["balance"] < bet: return jsonify({"detail": "Недостаточно Stars"}), 400
        new_balance = user["balance"] - bet + win_amount
        cursor.execute("UPDATE users SET balance = ?, total_wagered = total_wagered + ?, total_won = total_won + ? WHERE id = ?", (new_balance, bet, win_amount, user_id))
        conn.commit()
        return jsonify({"result": number, "color": color, "win": win, "win_amount": win_amount, "new_balance": new_balance})

@app.route('/api/games/blackjack/start', methods=['POST'])
def blackjack_start():
    user_id = str(request.args.get('user_id'))
    bet = int(request.args.get('bet', 10))
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, user_id)
        if user["balance"] < bet: return jsonify({"detail": "Недостаточно средств"}), 400
        win = random.choice([True, False])
        win_amount = bet * 2 if win else 0
        new_balance = user["balance"] - bet + win_amount
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
        return jsonify({"blackjack": win, "win_amount": win_amount, "player_hand": ["10", "A" if win else "7"], "dealer_hand": ["10", "9"]})

@app.route('/api/games/crash/bet', methods=['POST'])
def crash_bet():
    user_id = str(request.args.get('user_id'))
    bet = int(request.args.get('bet', 10))
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, user_id)
        if user["balance"] < bet: return jsonify({"detail": "Недостаточно средств"}), 400
        win = random.choice([True, False])
        mult = 2.1 if win else 1.2
        win_amount = int(bet * mult) if win else 0
        new_balance = user["balance"] - bet + win_amount
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
        return jsonify({"cashed_out": win, "multiplier": mult, "crash_point": mult, "win_amount": win_amount})

@app.route('/api/games/dice/roll', methods=['POST'])
def dice_roll():
    user_id = str(request.args.get('user_id'))
    bet = int(request.args.get('bet', 10))
    res = random.randint(1, 100)
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, user_id)
        if user["balance"] < bet: return jsonify({"detail": "Недостаточно средств"}), 400
        win = res > 50
        win_amount = bet * 2 if win else 0
        new_balance = user["balance"] - bet + win_amount
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
        return jsonify({"win": win, "result": res})

@app.route('/api/games/plinko/drop', methods=['POST'])
def plinko_drop():
    user_id = str(request.args.get('user_id'))
    bet = int(request.args.get('bet', 10))
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, user_id)
        if user["balance"] < bet: return jsonify({"detail": "Недостаточно средств"}), 400
        win = random.choice([True, False])
        win_amount = bet * 2 if win else 0
        new_balance = user["balance"] - bet + win_amount
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
        return jsonify({"win": win, "multiplier": 2 if win else 0, "win_amount": win_amount})

@app.route('/api/games/mines/start', methods=['POST'])
def mines_start():
    return jsonify({"status": "started"})

@app.route('/api/games/wheel/spin', methods=['POST'])
def wheel_spin():
    user_id = str(request.args.get('user_id'))
    bet = int(request.args.get('bet', 10))
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, user_id)
        if user["balance"] < bet: return jsonify({"detail": "Недостаточно средств"}), 400
        win = random.choice([True, False])
        win_amount = bet * 3 if win else 0
        new_balance = user["balance"] - bet + win_amount
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
        return jsonify({"win": win, "segment": {"name": "x3" if win else "0"}, "win_amount": win_amount})

@app.route('/api/games/aviator/bet', methods=['POST'])
def aviator_bet():
    user_id = str(request.args.get('user_id'))
    bet = int(request.args.get('bet', 10))
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, user_id)
        if user["balance"] < bet: return jsonify({"detail": "Недостаточно средств"}), 400
        win = random.choice([True, False])
        mult = 1.95
        win_amount = int(bet * mult) if win else 0
        new_balance = user["balance"] - bet + win_amount
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
        return jsonify({"cashed_out": win, "multiplier": mult, "crash_point": mult, "win_amount": win_amount})

@app.route('/api/daily_bonus/<user_id>', methods=['POST'])
def daily_bonus(user_id):
    today = str(date.today())
    with get_db() as conn:
        cursor = conn.cursor()
        user = ensure_user(cursor, str(user_id))
        if user["last_daily"] == today:
            return jsonify({"detail": "Бонус уже собран"}), 400
        cursor.execute("UPDATE users SET balance = balance + 50, free_spins = free_spins + 3, last_daily = ? WHERE id = ?", (today, str(user_id)))
        conn.commit()
        cursor.execute("SELECT balance, free_spins FROM users WHERE id = ?", (str(user_id),))
        row = cursor.fetchone()
        return jsonify({"bonus": 50, "free_spins": 3, "new_balance": row["balance"], "total_free_spins": row["free_spins"]})

@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id as username, total_won FROM users ORDER BY total_won DESC LIMIT 10")
        return jsonify([dict(r) for r in cursor.fetchall()])

@app.route('/api/referral/register', methods=['POST'])
def apply_referral():
    user_id = str(request.args.get('user_id'))
    code = (request.args.get('code') or '').strip().upper()
    with get_db() as conn:
        cursor = conn.cursor()
        ensure_user(cursor, user_id)
        cursor.execute("SELECT * FROM referrals WHERE referred_id = ?", (user_id,))
        if cursor.fetchone(): return jsonify({"detail": "Код уже активирован"}), 400
        cursor.execute("SELECT id FROM users WHERE UPPER(referral_code) = ?", (code,))
        referrer = cursor.fetchone()
        if not referrer or referrer["id"] == user_id: return jsonify({"detail": "Недействительный код"}), 400
        cursor.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer["id"], user_id))
        cursor.execute("UPDATE users SET balance = balance + 25 WHERE id = ?", (user_id,))
        cursor.execute("UPDATE users SET balance = balance + 50, referral_earnings = referral_earnings + 50 WHERE id = ?", (referrer["id"],))
        conn.commit()
        return jsonify({"status": "ok", "bonus": 25})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
