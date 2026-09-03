from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import uuid
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)

DATA_FILE = "data.json"

# ============ ЗАГРУЗКА ДАННЫХ ============
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        data = {
            "users": {},
            "nfts": {},
            "listings": {},
            "transactions": [],
            "referrals": {},
            "games": {
                "roulette": {"history": []},
                "slots": {"history": []}
            }
        }
        # Админ
        data["users"]["admin"] = {
            "id": "admin",
            "username": "Admin",
            "balance": 10000,
            "free_spins": 10,
            "level": 5,
            "xp": 0,
            "total_wagered": 0,
            "total_won": 0,
            "total_deposited": 0,
            "referral_code": "ADMIN123",
            "referred_by": None,
            "referrals": [],
            "referral_earnings": 0,
            "last_daily": None,
            "created_at": datetime.now().isoformat()
        }
        # Тестовые NFT
        nft_names = ["Cyber Dragon", "Neon Skull", "Space Sword", "Ghost Mask", 
                     "Pixel Hero", "Crypto Punk", "Meta Knight", "Galaxy Fox"]
        for i in range(10):
            nft_id = f"nft_{i+1}"
            data["nfts"][nft_id] = {
                "id": nft_id,
                "name": random.choice(nft_names) + f" #{i+1}",
                "image": f"https://picsum.photos/seed/{nft_id}/200/200",
                "owner_id": "admin",
                "rarity": random.choice(["common", "rare", "epic", "legendary"]),
                "price": random.randint(10, 100),
                "on_sale": False,
                "created_at": datetime.now().isoformat()
            }
        save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

def get_user(user_id):
    if user_id not in data["users"]:
        code = ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))
        data["users"][user_id] = {
            "id": user_id,
            "username": f"User_{user_id[:8]}",
            "balance": 100,
            "free_spins": 3,
            "level": 1,
            "xp": 0,
            "total_wagered": 0,
            "total_won": 0,
            "total_deposited": 0,
            "referral_code": code,
            "referred_by": None,
            "referrals": [],
            "referral_earnings": 0,
            "last_daily": None,
            "created_at": datetime.now().isoformat()
        }
        # Бесплатная NFT новому пользователю
        free_nft = {
            "id": f"nft_{uuid.uuid4().hex[:8]}",
            "name": "Welcome NFT",
            "image": f"https://picsum.photos/seed/{uuid.uuid4().hex[:8]}/200/200",
            "owner_id": user_id,
            "rarity": "common",
            "price": 0,
            "on_sale": False,
            "created_at": datetime.now().isoformat()
        }
        data["nfts"][free_nft["id"]] = free_nft
        save_data(data)
    return data["users"][user_id]

# ============ API ============

@app.route('/api/users/<user_id>', methods=['GET'])
def api_get_user(user_id):
    return jsonify(get_user(user_id))

@app.route('/api/nfts', methods=['GET'])
def api_get_nfts():
    return jsonify(list(data["nfts"].values()))

@app.route('/api/nfts/<user_id>', methods=['GET'])
def api_get_user_nfts(user_id):
    return jsonify([n for n in data["nfts"].values() if n["owner_id"] == user_id])

@app.route('/api/nfts/buy', methods=['POST'])
def api_buy_nft():
    user_id = request.args.get('user_id')
    nft_id = request.args.get('nft_id')
    
    if nft_id not in data["nfts"]:
        return jsonify({"error": "NFT not found"}), 404
    
    nft = data["nfts"][nft_id]
    if nft["owner_id"] == user_id:
        return jsonify({"error": "Already yours"}), 400
    
    user = get_user(user_id)
    price = nft.get("price", 50)
    
    if user["balance"] < price:
        return jsonify({"error": "Insufficient balance"}), 400
    
    seller = data["users"][nft["owner_id"]]
    user["balance"] -= price
    seller["balance"] += price
    nft["owner_id"] = user_id
    nft["on_sale"] = False
    save_data(data)
    
    return jsonify({"success": True, "new_balance": user["balance"]})

@app.route('/api/nfts/sell', methods=['POST'])
def api_sell_nft():
    user_id = request.args.get('user_id')
    nft_id = request.args.get('nft_id')
    price = int(request.args.get('price', 50))
    
    if nft_id not in data["nfts"]:
        return jsonify({"error": "NFT not found"}), 404
    
    nft = data["nfts"][nft_id]
    if nft["owner_id"] != user_id:
        return jsonify({"error": "Not yours"}), 403
    
    nft["price"] = price
    nft["on_sale"] = True
    save_data(data)
    return jsonify({"success": True})

@app.route('/api/nfts/transfer', methods=['POST'])
def api_transfer_nft():
    sender_id = request.args.get('sender_id')
    receiver_id = request.args.get('receiver_id')
    nft_id = request.args.get('nft_id')
    
    if nft_id not in data["nfts"]:
        return jsonify({"error": "NFT not found"}), 404
    
    nft = data["nfts"][nft_id]
    if nft["owner_id"] != sender_id:
        return jsonify({"error": "Not yours"}), 403
    
    get_user(receiver_id)
    nft["owner_id"] = receiver_id
    nft["on_sale"] = False
    save_data(data)
    return jsonify({"success": True})

@app.route('/api/market', methods=['GET'])
def api_get_market():
    return jsonify([n for n in data["nfts"].values() if n.get("on_sale", False)])

@app.route('/api/balance/add', methods=['POST'])
def api_add_balance():
    user_id = request.args.get('user_id')
    amount = int(request.args.get('amount', 0))
    
    user = get_user(user_id)
    user["balance"] += amount
    user["total_deposited"] += amount
    save_data(data)
    return jsonify({"success": True, "new_balance": user["balance"]})

@app.route('/api/balance/<user_id>', methods=['GET'])
def api_get_balance(user_id):
    user = get_user(user_id)
    return jsonify({"balance": user["balance"]})

# ============ РЕФЕРАЛЫ ============

@app.route('/api/referral/register', methods=['POST'])
def api_register_referral():
    user_id = request.args.get('user_id')
    code = request.args.get('code')
    
    user = get_user(user_id)
    if user.get("referred_by"):
        return jsonify({"error": "Already referred"}), 400
    
    for uid, u in data["users"].items():
        if u.get("referral_code") == code and uid != user_id:
            user["referred_by"] = uid
            u["referrals"].append(user_id)
            u["balance"] += 25
            u["referral_earnings"] += 25
            user["balance"] += 25
            save_data(data)
            return jsonify({"success": True, "bonus": 25})
    
    return jsonify({"error": "Invalid referral code"}), 404

@app.route('/api/referral/<user_id>', methods=['GET'])
def api_get_referral_info(user_id):
    user = get_user(user_id)
    return jsonify({
        "code": user.get("referral_code"),
        "referrals": user.get("referrals", []),
        "earnings": user.get("referral_earnings", 0),
        "count": len(user.get("referrals", []))
    })

# ============ ИГРЫ ============

@app.route('/api/games/slots/spin', methods=['POST'])
def slots_spin():
    user_id = request.args.get('user_id')
    bet = int(request.args.get('bet', 10))
    
    user = get_user(user_id)
    if user["balance"] < bet:
        return jsonify({"error": "Insufficient balance"}), 400
    
    symbols = ["🍒", "🍋", "🍊", "🍇", "🔔", "💎", "⭐", "7️⃣"]
    reels = [random.choice(symbols) for _ in range(9)]
    
    win = False
    win_amount = 0
    combo = ""
    lines = [[0,1,2], [3,4,5], [6,7,8], [0,4,8], [2,4,6], [0,3,6], [1,4,7], [2,5,8]]
    
    for line in lines:
        if reels[line[0]] == reels[line[1]] == reels[line[2]]:
            win = True
            symbol = reels[line[0]]
            combo = f"{symbol}{symbol}{symbol}"
            multipliers = {"🍒": 2, "🍋": 3, "🍊": 4, "🍇": 5, "🔔": 10, "💎": 20, "⭐": 50, "7️⃣": 100}
            win_amount = bet * multipliers.get(symbol, 2)
            break
    
    if win:
        user["balance"] += win_amount
        user["total_won"] += win_amount
    else:
        user["balance"] -= bet
    
    user["total_wagered"] += bet
    user["xp"] += bet // 10
    
    if user["xp"] >= (user["level"] * 100):
        user["level"] += 1
        user["xp"] = 0
    
    free_spins = 0
    if random.random() < 0.05:
        free_spins = random.randint(5, 15)
        user["free_spins"] += free_spins
    
    save_data(data)
    return jsonify({
        "reels": reels,
        "win": win,
        "win_amount": win_amount,
        "combo": combo,
        "new_balance": user["balance"],
        "free_spins": free_spins
    })

@app.route('/api/games/roulette/spin', methods=['POST'])
def roulette_spin():
    user_id = request.args.get('user_id')
    bet = int(request.args.get('bet', 10))
    bet_type = request.args.get('bet_type', 'red')
    
    user = get_user(user_id)
    if user["balance"] < bet:
        return jsonify({"error": "Insufficient balance"}), 400
    
    result = random.randint(0, 36)
    color = "red" if result in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "black" if result != 0 else "green"
    
    win = False
    win_amount = 0
    
    if bet_type == "red" and color == "red":
        win, win_amount = True, bet * 2
    elif bet_type == "black" and color == "black":
        win, win_amount = True, bet * 2
    elif bet_type == "green" and color == "green":
        win, win_amount = True, bet * 36
    elif bet_type == "even" and result % 2 == 0 and result != 0:
        win, win_amount = True, bet * 2
    elif bet_type == "odd" and result % 2 != 0:
        win, win_amount = True, bet * 2
    elif bet_type == "1-18" and 1 <= result <= 18:
        win, win_amount = True, bet * 2
    elif bet_type == "19-36" and 19 <= result <= 36:
        win, win_amount = True, bet * 2
    
    if win:
        user["balance"] += win_amount
        user["total_won"] += win_amount
    else:
        user["balance"] -= bet
    
    user["total_wagered"] += bet
    save_data(data)
    return jsonify({"result": result, "color": color, "win": win, "win_amount": win_amount, "new_balance": user["balance"]})

# ============ БОНУСЫ ============

@app.route('/api/daily_bonus/<user_id>', methods=['POST'])
def daily_bonus(user_id):
    user = get_user(user_id)
    today = datetime.now().date().isoformat()
    
    if user.get("last_daily") == today:
        return jsonify({"error": "Already claimed today"}), 400
    
    bonus = 10 + user["level"] * 5
    free_spins = 3 + user["level"]
    
    user["balance"] += bonus
    user["free_spins"] += free_spins
    user["last_daily"] = today
    save_data(data)
    
    return jsonify({
        "bonus": bonus,
        "free_spins": free_spins,
        "new_balance": user["balance"],
        "total_free_spins": user["free_spins"]
    })

# ============ СТАТИСТИКА ============

@app.route('/api/games/stats/<user_id>', methods=['GET'])
def get_stats(user_id):
    user = get_user(user_id)
    return jsonify({
        "level": user["level"],
        "xp": user["xp"],
        "total_wagered": user["total_wagered"],
        "total_won": user["total_won"],
        "total_deposited": user["total_deposited"],
        "free_spins": user["free_spins"],
        "referral_earnings": user.get("referral_earnings", 0),
        "referrals": len(user.get("referrals", []))
    })

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    users = []
    for uid, user in data["users"].items():
        users.append({
            "id": uid,
            "username": user.get("username", uid[:8]),
            "level": user.get("level", 1),
            "total_won": user.get("total_won", 0),
            "referrals": len(user.get("referrals", []))
        })
    users.sort(key=lambda x: x["total_won"], reverse=True)
    return jsonify(users[:10])

# ============ ПЛАТЕЖИ ============

@app.route('/api/payment/create_invoice', methods=['POST'])
def create_invoice():
    user_id = request.args.get('user_id')
    amount = int(request.args.get('amount', 0))
    
    if amount < 1:
        return jsonify({"error": "Min amount 1 ⭐"}), 400
    
    payment_id = f"pay_{uuid.uuid4().hex[:16]}"
    
    return jsonify({
        "success": True,
        "payment_id": payment_id,
        "amount": amount,
        "title": f"Deposit {amount} ⭐",
        "description": f"Add {amount} stars to your balance",
        "bot_username": "MinionsCasino_robot"
    })

# ============ ГЛАВНАЯ ============

@app.route('/')
def index():
    try:
        return send_file('67.html')
    except:
        return "<h1>File 67.html not found!</h1><p>Make sure 67.html is in the same folder</p>"

if __name__ == '__main__':
    print('=' * 50)
    print('🎰 MINIONS CASINO PREMIUM')
    print('📱 Open: http://localhost:8000')
    print('=' * 50)
    app.run(host='0.0.0.0', port=8000, debug=False)