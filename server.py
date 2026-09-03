import os
import random
import sqlite3
from datetime import date
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

DB_NAME = "casino.db"
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
        conn.commit()

        # Стартовые подарки/NFT для пользователя 8133727762
        ensure_user(cursor, TARGET_SELLER_ID)
        cursor.execute("SELECT COUNT(*) FROM nfts WHERE owner_id = ?", (TARGET_SELLER_ID,))
        if cursor.fetchone()[0] == 0:
            sample_gifts = [
                ("gift_cake_1", "Delicious Cake #4921", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC8xL1RhMW81OG9yOW9NLnBuZw.png", "Limited Gift", 150, TARGET_SELLER_ID, 1),
                ("gift_star_2", "Green Star #182", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC8yL1RhMW81OG9yOW9NLnBuZw.png", "Rare Gift", 300, TARGET_SELLER_ID, 1),
                ("gift_pepe_3", "Plush Pepe #88", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC8zL1RhMW81OG9yOW9NLnBuZw.png", "Legendary Gift", 750, TARGET_SELLER_ID, 1),
                ("gift_spark_4", "Party Sparkler #901", "https://cache.tonapi.io/imgproxy/T1_8hJ_mG6U/rs:fill:500:500:1/g:no/aHR0cHM6Ly90ZWxlZ3JhbS5vcmcvYmxvZy9maWxlLzgxMTE0MC80L1RhMW81OG9yOW9NLnBuZw.png", "Special Gift", 99, TARGET_SELLER_ID, 1)
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
        cursor.execute("INSERT INTO users (id, referral_code, balance) VALUES (?, ?, 1000)", (str(user_id), ref_code))
        cursor.execute("SELECT * FROM users WHERE id = ?", (str(user_id),))
        user = cursor.fetchone()
    return user

init_db()

@app.route('/')
def index():
    for f in ['67.html', 'index.html']:
        if os.path.exists(f):
            return send_file(f)
    return "<h1>Casino API</h1><p>HTML файл не найден</p>"

# Данные пользователя
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

# Депозит с комиссией 1%
@app.route('/api/balance/add', methods=['POST'])
def add_balance():
    data = request.get_json(silent=True) or {}
    user_id = str(request.args.get('user_id') or data.get('user_id') or '')
    amount = float(request.args.get('amount') or data.get('amount') or 0)
    currency = str(request.args.get('currency') or data.get('currency') or 'stars').lower()

    if not user_id or amount <= 0:
        return jsonify({"detail": "Некорректная сумма"}), 400

    net = amount * 0.99  # 1% комиссия: 100 -> 99 Stars, 1 -> 0.99 TON

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

# Маркет: только лоты пользователя 8133727762
@app.route('/api/market', methods=['GET'])
def get_market():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfts WHERE owner_id = ? AND is_for_sale = 1", (TARGET_SELLER_ID,))
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows])

# Инвентарь
@app.route('/api/nfts/<user_id>', methods=['GET'])
def get_user_nfts(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfts WHERE owner_id = ?", (str(user_id),))
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows])

# Настоящая покупка
@app.route('/api/nfts/buy', methods=['POST'])
def buy_nft():
    data = request.get_json(silent=True) or {}
    user_id = str(request.args.get('user_id') or data.get('user_id') or '')
    nft_id = str(request.args.get('nft_id') or data.get('nft_id') or '')

    with get_db() as conn:
        cursor = conn.cursor()
        buyer = ensure_user(cursor, user_id)

        cursor.execute("SELECT * FROM nfts WHERE id = ?", (nft_id,))
        nft = cursor.fetchone()

        if not nft or nft["is_for_sale"] != 1:
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

# Выставление на продажу
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

# Передача NFT
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

# Слоты
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

# Рулетка
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

# Ежедневный бонус
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

# Лидерборд
@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id as username, total_won FROM users ORDER BY total_won DESC LIMIT 10")
        return jsonify([dict(r) for r in cursor.fetchall()])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
