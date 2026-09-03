from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import uuid
import random
import hashlib
import time
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

DATA_FILE = "data.json"

# ============ НАСТРОЙКИ ============
BOT_TOKEN = "8909097529:AAHrqlwMZI1AD9XYcS3nFeEOksA07eEqJPU"
BOT_USERNAME = "MinionsCasino_robot"

# Комиссия 1%
STARS_COMMISSION = 0.01  # 100 → 99
TON_COMMISSION = 0.01    # 1 → 0.99

# ============ ДАННЫЕ ============
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
            "games": {"roulette": {"history": []}, "slots": {"history": []}},
            "pending_payments": {}
        }
        data["users"]["admin"] = {
            "id": "admin", "username": "Admin", "balance": 10000,
            "free_spins": 10, "level": 5, "xp": 0,
            "total_wagered": 0, "total_won": 0, "total_deposited": 0,
            "referral_code": "ADMIN123", "referred_by": None,
            "referrals": [], "referral_earnings": 0,
            "last_daily": None, "created_at": datetime.now().isoformat()
        }
        for i in range(10):
            nft_id = f"nft_{i+1}"
            data["nfts"][nft_id] = {
                "id": nft_id,
                "name": f"Legendary #{i+1}",
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
            "id": user_id, "username": f"User_{user_id[:8]}", "balance": 100,
            "free_spins": 3, "level": 1, "xp": 0,
            "total_wagered": 0, "total_won": 0, "total_deposited": 0,
            "referral_code": code, "referred_by": None,
            "referrals": [], "referral_earnings": 0,
            "last_daily": None, "created_at": datetime.now().isoformat()
        }
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

@app.route('/api/balance/<user_id>', methods=['GET'])
def api_get_balance(user_id):
    user = get_user(user_id)
    return jsonify({"balance": user["balance"]})

# ============ ПОПОЛНЕНИЕ ЧЕРЕЗ STARS ============

@app.route('/api/payment/stars/create', methods=['POST'])
def create_stars_payment():
    """Создаёт платеж через Telegram Stars с комиссией 1%"""
    user_id = request.args.get('user_id')
    amount = int(request.args.get('amount', 0))
    
    if amount < 1:
        return jsonify({"error": "Минимальная сумма 1 ⭐"}), 400
    
    # Вычисляем с комиссией (1%)
    net_amount = int(amount * (1 - STARS_COMMISSION))
    
    payment_id = f"stars_{uuid.uuid4().hex[:16]}"
    
    # Сохраняем платеж
    data["pending_payments"][payment_id] = {
        "id": payment_id,
        "user_id": user_id,
        "amount": amount,
        "net_amount": net_amount,
        "type": "stars",
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    save_data(data)
    
    # Ссылка для оплаты через Telegram Stars
    # Формат: https://t.me/bot_username?start=pay_stars_XXX
    invoice_link = f"https://t.me/{BOT_USERNAME}?start=pay_stars_{payment_id}_{user_id}_{amount}"
    
    return jsonify({
        "success": True,
        "payment_id": payment_id,
        "invoice_link": invoice_link,
        "amount": amount,
        "net_amount": net_amount,
        "commission": f"{STARS_COMMISSION * 100}%",
        "message": f"Пополнение {amount} ⭐ → {net_amount} ⭐ на баланс (комиссия 1%)"
    })

@app.route('/api/payment/stars/confirm', methods=['POST'])
def confirm_stars_payment():
    """Подтверждение оплаты Stars (вызывается после успешной оплаты)"""
    payment_id = request.args.get('payment_id')
    user_id = request.args.get('user_id')
    
    if payment_id not in data["pending_payments"]:
        return jsonify({"error": "Платёж не найден"}), 404
    
    payment = data["pending_payments"][payment_id]
    if payment["status"] != "pending":
        return jsonify({"error": "Платёж уже обработан"}), 400
    
    payment["status"] = "completed"
    payment["completed_at"] = datetime.now().isoformat()
    
    # Начисляем баланс (с комиссией)
    user = get_user(user_id)
    net_amount = payment["net_amount"]
    user["balance"] += net_amount
    user["total_deposited"] += net_amount
    
    # Записываем транзакцию
    data["transactions"].append({
        "id": payment_id,
        "user_id": user_id,
        "type": "stars_deposit",
        "amount": payment["amount"],
        "net_amount": net_amount,
        "commission": payment["amount"] - net_amount,
        "status": "completed",
        "created_at": payment["created_at"],
        "completed_at": payment["completed_at"]
    })
    
    save_data(data)
    
    return jsonify({
        "success": True,
        "new_balance": user["balance"],
        "net_amount": net_amount,
        "message": f"Пополнено {net_amount} ⭐ (с комиссией 1%)"
    })

# ============ ПОПОЛНЕНИЕ ЧЕРЕЗ TON ============

@app.route('/api/payment/ton/create', methods=['POST'])
def create_ton_payment():
    """Создаёт платёж через TON с комиссией 1%"""
    user_id = request.args.get('user_id')
    amount = float(request.args.get('amount', 0))
    
    if amount < 0.1:
        return jsonify({"error": "Минимальная сумма 0.1 TON"}), 400
    
    # Вычисляем с комиссией (1%)
    net_amount = round(amount * (1 - TON_COMMISSION), 2)
    
    payment_id = f"ton_{uuid.uuid4().hex[:16]}"
    
    # Генерируем кошелёк для депозита (в реальном проекте используй TON API)
    # Здесь используем тестовый адрес
    wallet_address = "EQD...test_wallet_address..."
    
    data["pending_payments"][payment_id] = {
        "id": payment_id,
        "user_id": user_id,
        "amount": amount,
        "net_amount": net_amount,
        "type": "ton",
        "wallet": wallet_address,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    save_data(data)
    
    return jsonify({
        "success": True,
        "payment_id": payment_id,
        "wallet_address": wallet_address,
        "amount": amount,
        "net_amount": net_amount,
        "commission": f"{TON_COMMISSION * 100}%",
        "message": f"Отправьте {amount} TON на кошелёк. Получите {net_amount} ⭐ на баланс (комиссия 1%)"
    })

@app.route('/api/payment/ton/confirm', methods=['POST'])
def confirm_ton_payment():
    """Подтверждение оплаты TON (проверка транзакции)"""
    payment_id = request.args.get('payment_id')
    user_id = request.args.get('user_id')
    tx_hash = request.args.get('tx_hash')
    
    if payment_id not in data["pending_payments"]:
        return jsonify({"error": "Платёж не найден"}), 404
    
    payment = data["pending_payments"][payment_id]
    if payment["status"] != "pending":
        return jsonify({"error": "Платёж уже обработан"}), 400
    
    # В реальном проекте здесь проверка транзакции через TON API
    # Для демонстрации считаем, что платеж подтверждён
    
    payment["status"] = "completed"
    payment["tx_hash"] = tx_hash
    payment["completed_at"] = datetime.now().isoformat()
    
    user = get_user(user_id)
    net_amount = payment["net_amount"]
    user["balance"] += net_amount
    user["total_deposited"] += net_amount
    
    data["transactions"].append({
        "id": payment_id,
        "user_id": user_id,
        "type": "ton_deposit",
        "amount": payment["amount"],
        "net_amount": net_amount,
        "commission": payment["amount"] - net_amount,
        "tx_hash": tx_hash,
        "status": "completed",
        "created_at": payment["created_at"],
        "completed_at": payment["completed_at"]
    })
    
    save_data(data)
    
    return jsonify({
        "success": True,
        "new_balance": user["balance"],
        "net_amount": net_amount,
        "message": f"Пополнено {net_amount} ⭐ (с комиссией 1%)"
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
        "reels": reels, "win": win, "win_amount": win_amount,
        "combo": combo, "new_balance": user["balance"],
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

@app.route('/api/games/blackjack/start', methods=['POST'])
def blackjack_start():
    user_id = request.args.get('user_id')
    bet = int(request.args.get('bet', 10))
    user = get_user(user_id)
    if user["balance"] < bet:
        return jsonify({"error": "Insufficient balance"}), 400
    
    deck = [2,3,4,5,6,7,8,9,10,10,10,10,11] * 4
    random.shuffle(deck)
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    player_total = sum(player_hand)
    
    if player_total == 21:
        user["balance"] += int(bet * 1.5)
        save_data(data)
        return jsonify({"win": True, "blackjack": True, "win_amount": int(bet * 1.5), "new_balance": user["balance"]})
    
    return jsonify({
        "player_hand": player_hand,
        "dealer_hand": [dealer_hand[0], "?"],
        "bet": bet,
        "game_id": str(uuid.uuid4())
    })

@app.route('/api/games/crash/bet', methods=['POST'])
def crash_bet():
    user_id = request.args.get('user_id')
    bet = int(request.args.get('bet', 10))
    user = get_user(user_id)
    if user["balance"] < bet:
        return jsonify({"error": "Insufficient balance"}), 400
    
    crash_point = round(random.uniform(1.0, 50.0), 2)
    cash_out = random.choice([True, False])
    
    if cash_out and crash_point > 1.0:
        multiplier = round(random.uniform(1.1, crash_point), 2)
        win_amount = int(bet * multiplier)
        user["balance"] += win_amount
        user["total_won"] += win_amount
        result = {"cashed_out": True, "multiplier": multiplier, "win_amount": win_amount}
    else:
        user["balance"] -= bet
        result = {"cashed_out": False, "crash_point": crash_point, "win_amount": 0}
    
    user["total_wagered"] += bet
    save_data(data)
    return jsonify({**result, "new_balance": user["balance"]})

@app.route('/api/games/dice/roll', methods=['POST'])
def dice_roll():
    user_id = request.args.get('user_id')
    bet = int(request.args.get('bet', 10))
    prediction = request.args.get('prediction', 'over')
    target = int(request.args.get('target', 50))
    user = get_user(user_id)
    if user["balance"] < bet:
        return jsonify({"error": "Insufficient balance"}), 400
    
    result = random.randint(1, 100)
    win = False
    
    if prediction == "over" and result > target:
        win = True
    elif prediction == "under" and result < target:
        win = True
    elif prediction == "exact" and result == target:
        win = True
    
    if win:
        multiplier = 100 / target if prediction == "under" else 100 / (100 - target)
        win_amount = int(bet * multiplier)
        user["balance"] += win_amount
        user["total_won"] += win_amount
    else:
        win_amount = 0
        user["balance"] -= bet
    
    user["total_wagered"] += bet
    save_data(data)
    return jsonify({"result": result, "win": win, "win_amount": win_amount, "new_balance": user["balance"]})

@app.route('/api/games/plinko/drop', methods=['POST'])
def plinko_drop():
    user_id = request.args.get('user_id')
    bet = int(request.args.get('bet', 10))
    risk = request.args.get('risk', 'medium')
    user = get_user(user_id)
    if user["balance"] < bet:
        return jsonify({"error": "Insufficient balance"}), 400
    
    multipliers = {
        "low": [0.5, 0.5, 1, 1.5, 2, 1.5, 1, 0.5, 0.5],
        "medium": [0.2, 0.5, 1, 2, 4, 2, 1, 0.5, 0.2],
        "high": [0.1, 0.3, 0.8, 2.5, 8, 2.5, 0.8, 0.3, 0.1]
    }
    
    path = [random.choice([-1, 1]) for _ in range(8)]
    position = 4 + sum(path)
    position = max(0, min(8, position))
    multiplier = multipliers.get(risk, multipliers["medium"])[position]
    win_amount = int(bet * multiplier) if multiplier > 1 else 0
    
    if multiplier > 1:
        user["balance"] += win_amount
        user["total_won"] += win_amount
    else:
        user["balance"] -= bet
    
    user["total_wagered"] += bet
    save_data(data)
    return jsonify({"position": position, "multiplier": multiplier, "win": multiplier > 1, "win_amount": win_amount, "new_balance": user["balance"]})

@app.route('/api/games/wheel/spin', methods=['POST'])
def wheel_spin():
    user_id = request.args.get('user_id')
    bet = int(request.args.get('bet', 10))
    user = get_user(user_id)
    if user["balance"] < bet:
        return jsonify({"error": "Insufficient balance"}), 400
    
    segments = [
        {"name": "x0", "multiplier": 0, "color": "#ff4444", "chance": 10},
        {"name": "x1", "multiplier": 1, "color": "#ff8800", "chance": 20},
        {"name": "x2", "multiplier": 2, "color": "#ffcc00", "chance": 20},
        {"name": "x3", "multiplier": 3, "color": "#44ff44", "chance": 15},
        {"name": "x5", "multiplier": 5, "color": "#44ccff", "chance": 10},
        {"name": "x10", "multiplier": 10, "color": "#8844ff", "chance": 5},
        {"name": "x20", "multiplier": 20, "color": "#ff44ff", "chance": 3},
        {"name": "x50", "multiplier": 50, "color": "#ff0000", "chance": 1}
    ]
    
    total = sum(s["chance"] for s in segments)
    r = random.randint(1, total)
    for seg in segments:
        r -= seg["chance"]
        if r <= 0:
            selected = seg
            break
    
    win = selected["multiplier"] > 0
    win_amount = bet * selected["multiplier"] if win else 0
    
    if win:
        user["balance"] += win_amount
        user["total_won"] += win_amount
    else:
        user["balance"] -= bet
    
    user["total_wagered"] += bet
    save_data(data)
    return jsonify({"segment": selected, "win": win, "win_amount": win_amount, "new_balance": user["balance"]})

@app.route('/api/games/aviator/bet', methods=['POST'])
def aviator_bet():
    user_id = request.args.get('user_id')
    bet = int(request.args.get('bet', 10))
    user = get_user(user_id)
    if user["balance"] < bet:
        return jsonify({"error": "Insufficient balance"}), 400
    
    multiplier = round(random.uniform(1.0, 10.0), 2)
    cashed_out = random.choice([True, False])
    
    if cashed_out and multiplier > 1.0:
        cash_mult = round(random.uniform(1.1, multiplier), 2)
        win_amount = int(bet * cash_mult)
        user["balance"] += win_amount
        user["total_won"] += win_amount
        result = {"cashed_out": True, "multiplier": cash_mult, "win_amount": win_amount}
    else:
        user["balance"] -= bet
        result = {"cashed_out": False, "crash_point": multiplier, "win_amount": 0}
    
    user["total_wagered"] += bet
    save_data(data)
    return jsonify({**result, "new_balance": user["balance"]})

@app.route('/api/games/mines/start', methods=['POST'])
def mines_start():
    user_id = request.args.get('user_id')
    bet = int(request.args.get('bet', 10))
    mines = int(request.args.get('mines', 3))
    user = get_user(user_id)
    if user["balance"] < bet:
        return jsonify({"error": "Insufficient balance"}), 400
    return jsonify({"grid": [["⬜" for _ in range(5)] for _ in range(5)], "mines": mines, "bet": bet, "game_id": str(uuid.uuid4())})

# ============ БОНУСЫ И СТАТИСТИКА ============

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
    return jsonify({"bonus": bonus, "free_spins": free_spins, "new_balance": user["balance"], "total_free_spins": user["free_spins"]})

@app.route('/api/games/stats/<user_id>', methods=['GET'])
def get_stats(user_id):
    user = get_user(user_id)
    return jsonify({
        "level": user["level"], "xp": user["xp"],
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

@app.route('/')
def index():
    try:
        return send_file('index.html')
    except:
        return "<h1>File index.html not found!</h1>"

if __name__ == '__main__':
    print('=' * 50)
    print('🎰 MINIONS CASINO')
    print('📱 Open: http://localhost:8000')
    print('⭐ Stars: 100 → 99 (комиссия 1%)')
    print('💎 TON: 1 → 0.99 (комиссия 1%)')
    print('=' * 50)
    app.run(host='0.0.0.0', port=8000, debug=False)
