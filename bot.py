import asyncio
import math
import time
import json
import hashlib
import logging
import httpx
import random
from typing import Optional
import requests
from telegram import ReplyKeyboardMarkup, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ExtBot, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
)
import unicodedata
from datetime import datetime, timedelta
from flask import Flask, request
import threading

# Flask app for Render
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Lotus Super Bot 6 Lottery is running!"

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Platform URLs
PLATFORM_URLS = {
    "6lottery": "https://6lotteryapi.com/api/webapi/",
    "Cklottery": "https://ckygjf6r.com/api/webapi/",
    "777bigwingame": "https://api.bigwinqaz.com/api/webapi/"
}

# Platform display names
PLATFORM_NAMES = {
    "6lottery": "🔴 6lottery",
    "Cklottery": "🔵 Cklottery",
    "777bigwingame": "🟢 777bigwin"
}

# Config
BOT_TOKEN = "8611174345:AAFAEhsH5ZvKso08kJD-A4wqlCv6b2sot4M" 
IGNORE_SSL = True
WIN_LOSE_CHECK_INTERVAL = 3
MAX_RESULT_WAIT_TIME = 90
ADMIN_ID = 6736719959
MAX_BALANCE_RETRIES = 10
BALANCE_RETRY_DELAY = 5
BALANCE_API_TIMEOUT = 30
BET_API_TIMEOUT = 45
MAX_BET_RETRIES = 3
BET_RETRY_DELAY = 5
MAX_CONSECUTIVE_ERRORS = 10
MESSAGE_RATE_LIMIT_SECONDS = 10
MAX_TELEGRAM_RETRIES = 3
TELEGRAM_RETRY_DELAY = 2

# Strategy names mapping
STRATEGY_NAMES = {
    "Mr King": "👑 Mr King",
    "V 1": "💎 V 1", 
    "Lottery Father": "🎰 Lottery Father",
    "AI WAVE": "🤖 AI WAVE",
    "AI King": "🤖 AI King",
    "AI Chat": "🤖 AI Chat",
    "Lottery Follow": "📈 Lottery Follow",
    "Lottery Brain": "🧠 Lottery Brain",
    "Manual": "📝 Manual BS",
    "KM_Enhance": "⭐ KM_Enhance"
}

# Global storage
user_state = {}
user_temp = {}
user_sessions = {}
user_settings = {}
user_pending_bets = {}
user_waiting_for_result = {}
user_stats = {}
user_game_info = {}
allowed_user_ids = {}  # user_id -> ingame_id for authorization
next_bet_time = None
next_bet_issue = None
streak_bet_count = 0

# Persistence helpers
def load_allowed_users():
    global allowed_user_ids
    try:
        with open('allowed_users.json', 'r') as f:
            data = json.load(f)
            allowed_user_ids = data.get('allowed_users', {})
            logging.info(f"Loaded {len(allowed_user_ids)} authorized users")
    except FileNotFoundError:
        logging.warning("allowed_users.json not found. Starting fresh")
        allowed_user_ids = {}
    except Exception as e:
        logging.error(f"Error loading allowed_users.json: {e}")
        allowed_user_ids = {}

def save_allowed_users():
    global allowed_user_ids
    try:
        with open('allowed_users.json', 'w') as f:
            json.dump({'allowed_users': allowed_user_ids}, f, indent=4)
            logging.info(f"Saved {len(allowed_user_ids)} authorized users")
    except Exception as e:
        logging.error(f"Error saving user list: {e}")

# Helper functions
def normalize_text(text: str) -> str:
    return unicodedata.normalize('NFKC', text).strip()

def sign_md5(data: dict) -> str:
    filtered = {k: v for k, v in data.items() if k not in ("signature", "timestamp")}
    sort_map = dict(sorted(filtered.items()))
    json_str = json.dumps(sort_map, separators=(',', ':'))
    md5_hash = hashlib.md5(json_str.encode("utf-8")).hexdigest().upper()
    return md5_hash

def sign_md5_original(data: dict) -> str:
    data_copy = dict(data)
    data_copy.pop("signature", None)
    data_copy.pop("timestamp", None)
    s = json.dumps(dict(sorted(data_copy.items())), separators=(',', ':'))
    return hashlib.md5(s.encode("utf-8")).hexdigest().upper()

def compute_unit_amount(_amt: int) -> int:
    if _amt <= 0:
        return 1
    amt_str = str(_amt)
    trailing_zeros = len(amt_str) - len(amt_str.rstrip('0'))
    if trailing_zeros == 4:
        return 10000
    elif trailing_zeros == 3:
        return 1000
    elif trailing_zeros == 2:
        return 100
    elif trailing_zeros == 1:
        return 10
    else:
        length = len(amt_str)
        return 10 ** (length - 1)

def get_select_map(game_type: str):
    if game_type == "TRX":
        return {"B": 13, "S": 14}
    return {"B": 13, "S": 14}

def calculate_blockid_sum(block_id: str) -> int:
    digits = [int(c) for c in block_id if c.isdigit()]
    total = sum(digits)
    while total > 9:
        total = sum(int(d) for d in str(total))
    return total

def get_random_interval():
    if random.random() < 0.4:
        return random.randint(10, 20)
    return random.randint(20, 40)

def get_strategy_display_name(settings: dict) -> str:
    """Get strategy display name without revealing the pattern"""
    pattern_type = settings.get("pattern_type", "sequential")
    
    if pattern_type == "lottery_follow":
        return "📈 Lottery Follow"
    elif pattern_type == "lottery_brain":
        return "🧠 Lottery Brain"
    elif pattern_type == "sequential":
        pattern = settings.get("pattern", "")
        if pattern == "SBSBSBBSBSBBSBBSSBSBSBBBSBBBSSSBSBSBBSBSSSBSSSBBBBSSSBSBSBBBSSSSBBBBBSBSSSBSSSBSSBBBSBSS":
            return "👑 Mr King"
        elif pattern == "SBSSSBBBBBSSBBSSSBBSSSBSSBBBSBBSSBSSBSBSBSSSBBSBSSSSSBBBSBBSBBBSBSBBBBSBSSBBSSSBBBSSBSBSBBBBSBS":
            return "💎 V 1"
        elif pattern == "BSBBSBSSBSSBSBBSBBSBSSBBSBSSBSBSSSSBSBBBBSSSSSSSBSSSBBSBBSBSSBSSBSBBSSSSSSSBSSSBBSSSSBSBBBBSBBSBSSBBSBSSBS":
            return "🎰 Lottery Father"
        elif pattern == "SSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSS":
            return "🤖 AI WAVE"
        elif pattern == "SSBBSSSSSBSSBBSSBSSBBBBSBSS":
            return "🤖 AI King"
        elif pattern == "BSBBSBBSBSSSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSSBSBSBSBSBSBBSSBSSBBSBSSBBSBBSSBBBSSSSSBBSBBSSBSSBBBSBSSSBSBBSSBSBBBSBBBBSSSSSBBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSSSSSBBBBBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSBBBBSSSSSBBBBSSBSBBBSBBSSBSSBBSBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSBBSSBSSBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBBBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSBSBSSBSSBSBBBSSBBBBBSBBSSSSBSBBSBBSBSSBBSSSBSBBBSBBBBSSBBBBBSBBSSSBBBSBBBSBBBSBBBSBBSSBSSSBBSSBBSSBBBSBBBSBBBSBBBBBSSSSSSBBSSSSBSBSSSSBBSSSSBBSSSSSBSSSSBSBBBSBBBSBBSSBBBSBBBSBBBSBBBSBBSBSBSBSBSBSBBSSBSSBBSBSSBBSBBSSBBBSSSSSBBSBBSSBSSBBBSBSSSBSBBSSBSBBBSBBBBSSSSSBBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSSSSSBBBBBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSBBBBSSSSSBBBBSSBSBBBSBBSSBSSBBSBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSBBSSBSSBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBBBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSB":
            return "🤖 AI Chat"
        elif pattern == "BSSBSSBSBBSBSBSBBSBSBBSSBBSBSBBSBSBBSBBSBBBSBSSSBBBBB":
            return "⭐ KM_Enhance"
        else:
            return "📝 Manual BS"
    return "Unknown"

def apply_formula_mode(ch: str, formula_mode: str, last_result: str = None) -> str:
    """Apply formula mode to the prediction"""
    if formula_mode == "straight":
        return ch
    elif formula_mode == "reverse":
        return "B" if ch == "S" else "S"
    elif formula_mode == "back":
        return "B" if ch == "S" else "S"
    else:
        return ch

# API wrappers
def login_request(phone: str, password: str, base_url: str) -> (Optional[dict], Optional[requests.Session]):
    session = requests.Session()
    body = {
        "phonetype": -1, "language": 0, "logintype": "mobile",
        "random": "9078efc98754430e92e51da59eb2563c",
        "username": "95" + phone, "pwd": password
    }
    body["signature"] = sign_md5_original(body).upper()
    body["timestamp"] = int(time.time())
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; Mobile Build/QP1A.190711.020)",
        "Connection": "Keep-Alive", "Accept-Encoding": "gzip"
    }
    try:
        r = session.post(base_url + "Login", headers=headers, json=body, timeout=12, verify=not IGNORE_SSL)
        res = r.json()
        if res.get("code") == 0 and "data" in res:
            token_header = res["data"].get("tokenHeader", "Bearer ")
            token = res["data"].get("token", "")
            session.headers.update({"Authorization": f"{token_header}{token}"})
            session.base_url = base_url
            return res, session
        return res, None
    except Exception as e:
        logging.error(f"Login error: {e}")
        return {"error": str(e)}, None

async def get_user_info(session: requests.Session, user_id: int) -> Optional[dict]:
    base_url = session.base_url
    body = {"language": 0, "random": "9078efc98754430e92e51da59eb2563c"}
    body["signature"] = sign_md5_original(body).upper()
    body["timestamp"] = int(time.time())
    try:
        r = session.post(base_url + "GetUserInfo", json=body, timeout=12, verify=not IGNORE_SSL)
        res = r.json()
        if isinstance(res, dict) and res.get("code") == 0 and "data" in res:
            info = {
                "user_id": res["data"].get("userId"), "username": res["data"].get("userName"),
                "nickname": res["data"].get("nickName"), "balance": res["data"].get("amount"),
                "photo": res["data"].get("userPhoto"), "login_date": res["data"].get("userLoginDate"),
                "withdraw_count": res["data"].get("withdrawCount"),
                "is_allow_withdraw": res["data"].get("isAllowWithdraw", 0) == 1
            }
            user_game_info[user_id] = info
            return info
    except Exception as e:
        logging.error(f"Get user info error: {e}")
    return None

async def get_balance(session: requests.Session, user_id: int) -> Optional[float]:
    base_url = session.base_url
    body = {"language": 0, "random": "9078efc6f3794bf49f257d07937d1a29"}
    body["signature"] = sign_md5_original(body).upper()
    body["timestamp"] = int(time.time())
    try:
        r = session.post(base_url + "GetBalance", json=body, timeout=BALANCE_API_TIMEOUT, verify=not IGNORE_SSL)
        res = r.json()
        logging.info(f"စာရင်းစစ်ဆေးမှု အသုံးပြုသူ {user_id} အတွက်: {res}")
        if isinstance(res, dict) and res.get("code") == 0 and "data" in res:
            data = res.get("data", {})
            amount = data.get("Amount") or data.get("amount") or data.get("balance")
            if amount is not None:
                if user_id in user_game_info:
                    user_game_info[user_id]["balance"] = float(amount)
                if user_id not in user_stats:
                    user_stats[user_id] = {"start_balance": float(amount), "profit": 0.0}
                return float(amount)
            logging.warning(f"စာရင်းပမာဏမတွေ့ရပါ အသုံးပြုသူ {user_id} အတွက်: {res}")
        else:
            logging.error(f"စာရင်းစစ်ဆေးမှု မအောင်မြင်ပါ အသုံးပြုသူ {user_id} အတွက်: {res.get('msg', 'အမည်မသိအမှား')}")
    except Exception as e:
        logging.error(f"စာရင်းစစ်ဆေးမှု အမှား အသုံးပြုသူ {user_id} အတွက်: {e}")
    return None

def get_game_issue_request(session: requests.Session, game_type: str) -> dict:
    base_url = session.base_url
    body = {"typeId": 13 if game_type == "TRX" else 1, "language": 0, "random": "b05034ba4a2642009350ee863f29e2e9"}
    body["signature"] = sign_md5(body).upper()
    body["timestamp"] = int(time.time())
    try:
        endpoint = "GetTrxGameIssue" if game_type == "TRX" else "GetGameIssue"
        r = session.post(base_url + endpoint, json=body, timeout=12, verify=not IGNORE_SSL)
        logging.debug(f"ဂိမ်းထုတ်ပြန်မှု {game_type} အတွက်: {r.json()}")
        return r.json()
    except Exception as e:
        logging.error(f"ဂိမ်းထုတ်ပြန်မှုအမှား {game_type} အတွက်: {e}")
        return {"error": str(e)}

async def place_bet_request(session: requests.Session, issue_number: str, select_type: int, _amt: int, game_type: str, user_id: int) -> dict:
    base_url = session.base_url
    unit_amount = compute_unit_amount(_amt)
    bet_count = int(_amt / unit_amount) if unit_amount > 0 else 1
    betBody = {
        "typeId": 13 if game_type == "TRX" else 1, "issuenumber": issue_number, "language": 0,
        "gameType": 2, "amount": int(unit_amount), "betCount": int(bet_count),
        "selectType": select_type, "random": "9078efc98754430e92e51da59eb2563c"
    }
    betBody["signature"] = sign_md5_original(betBody).upper()
    betBody["timestamp"] = int(time.time())
    endpoint = "GameTrxBetting" if game_type == "TRX" else "GameBetting"
    for attempt in range(MAX_BET_RETRIES):
        try:
            r = session.post(base_url + endpoint, json=betBody, timeout=BET_API_TIMEOUT, verify=not IGNORE_SSL)
            res = r.json()
            logging.info(f"လောင်းကြေးထည့်သွင်းမှု အသုံးပြုသူ {user_id}, {game_type}, အကြိမ်ရေ {issue_number}, အမျိုးအစား {select_type}, ပမာဏ {_amt}: {res}")
            return res
        except requests.exceptions.Timeout as e:
            logging.warning(f"လောင်းကြေးအချိန်ကုန်သွားပါပြီ အသုံးပြုသူ {user_id}, {game_type}, အကြိမ်ရေ {issue_number}, အကြိမ် {attempt + 1}/{MAX_BET_RETRIES}: {str(e)}")
            if attempt < MAX_BET_RETRIES - 1:
                if user_id in user_game_info and user_id in user_temp:
                    username = user_game_info[user_id].get("username", "").replace("95", "", 1)
                    password = user_temp.get(user_id, {}).get("password")
                    platform = user_settings.get(user_id, {}).get("platform")
                    if username and password and platform and platform in PLATFORM_URLS:
                        logging.info(f"ပြန်လည်စတင်ရန် ကြိုးစားနေပါသည် အသုံးပြုသူ {user_id} အတွက်")
                        base_url = PLATFORM_URLS[platform]
                        res, new_session = login_request(username, password, base_url)
                        if new_session:
                            user_sessions[user_id] = new_session
                            session = new_session
                            logging.info(f"ပြန်လည်ဝင်ရောက်မှု အောင်မြင်ပါသည် အသုံးပြုသူ {user_id} အတွက်")
                        else:
                            logging.error(f"ပြန်လည်ဝင်ရောက်မှု မအောင်မြင်ပါ အသုံးပြုသူ {user_id} အတွက်: {res.get('msg', 'အမည်မသိအမှား')}")
                await asyncio.sleep(BET_RETRY_DELAY)
                continue
            logging.error(f"လောင်းကြေးထည့်သွင်းမှု မအောင်မြင်ပါ {MAX_BET_RETRIES} ကြိမ်အထိ အသုံးပြုသူ {user_id} အတွက်: အချိန်ကုန်သွားပါပြီ")
            return {"error": f"လောင်းကြေးထည့်သွင်းမှု အချိန်ကုန်သွားပါပြီ {MAX_BET_RETRIES} ကြိမ်အထိ"}
        except Exception as e:
            logging.error(f"လောင်းကြေးထည့်သွင်းမှု အမှား အသုံးပြုသူ {user_id} အတွက်: {str(e)}")
            if attempt < MAX_BET_RETRIES - 1:
                await asyncio.sleep(BET_RETRY_DELAY)
                continue
            return {"error": str(e)}
    return {"error": "ကြိုးစားမှုများပြီးနောက် မအောင်မြင်ပါ"}

def get_noaverage_emerd_list_request(session: requests.Session) -> dict:
    base_url = session.base_url
    body = {
        "pageSize": 10,
        "typeId": 1,
        "language": 7,
        "random": "f15bdcc4e6a04f8f828c4627baea8434",
        "signature": "5436315B4844CE16E7AB5BFB42A8FC3B",
        "timestamp": int(time.time())
    }
    headers = {"Content-Type": "application/json"}
    try:
        r = session.post(base_url + "GetNoaverageEmerdList", headers=headers, json=body, timeout=12, verify=not IGNORE_SSL)
        logging.debug(f"ရလဒ်စာရင်းတုံ့ပြန်မှု: {r.json()}")
        return r.json()
    except Exception as e:
        logging.error(f"ရလဒ်စာရင်းအမှား: {e}")
        return {"error": str(e), "code": -1}

async def send_message_with_retry(bot, chat_id: int, text: str, reply_markup=None):
    for attempt in range(MAX_TELEGRAM_RETRIES):
        try:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
            logging.info(f"စာတိုပေးပို့ပြီးပါပြီ {chat_id}: {text}")
            return True
        except Exception as e:
            logging.error(f"စာတိုပေးပို့မရပါ {chat_id}, အကြိမ် {attempt + 1}/{MAX_TELEGRAM_RETRIES}: {str(e)}")
            if attempt < MAX_TELEGRAM_RETRIES - 1:
                await asyncio.sleep(TELEGRAM_RETRY_DELAY)
                continue
            return False
    return False

async def get_user_balance(session: requests.Session, user_id: int) -> Optional[float]:
    settings = user_settings.get(user_id, {})
    if settings.get("bank_mode") == "DEMO":
        demo_balance = settings.get("demo_balance", 0.0)
        logging.info(f"အခမဲ့စာရင်း အသုံးပြုသူ {user_id} အတွက်: {demo_balance}")
        return demo_balance
    else:
        return await get_balance(session, user_id)

def update_demo_balance(user_id: int, amount: float, is_win: bool = False):
    settings = user_settings.get(user_id, {})
    if settings.get("bank_mode") == "DEMO":
        current_balance = settings.get("demo_balance", 0.0)
        if is_win:
            new_balance = current_balance + amount
        else:
            new_balance = current_balance - amount
        settings["demo_balance"] = max(0, new_balance)
        logging.info(f"အခမဲ့စာရင်း အပ်ဒိတ်လုပ်ပြီး အသုံးပြုသူ {user_id}: {current_balance} -> {settings['demo_balance']} (အနိုင်: {is_win}, ပမာဏ: {amount})")
        return settings["demo_balance"]
    return None

async def win_lose_checker(context: ContextTypes.DEFAULT_TYPE):
    logging.info("အနိုင်/အရှုံး စစ်ဆေးရေး စတင်နေပါပြီ")
    while True:
        try:
            current_users = list(user_sessions.keys())
            for user_id in current_users:
                try:
                    session = user_sessions.get(user_id)
                    if not session:
                        continue
                        
                    settings = user_settings.get(user_id, {})
                    if not settings.get("running", False):
                        continue
                        
                    game_type = settings.get("game_type", "WINGO")
                    
                    try:
                        if game_type == "WINGO":
                            issue_res = get_noaverage_emerd_list_request(session)
                        else:
                            issue_res = get_game_issue_request(session, game_type)
                        
                        if not isinstance(issue_res, dict) or issue_res.get("code") != 0:
                            logging.warning(f"ဂိမ်းဒေတာရယူရန် မအောင်မြင်ပါ အသုံးပြုသူ {user_id}: {issue_res}")
                            continue
                            
                        if game_type == "WINGO":
                            data = issue_res.get("data", {}).get("list", [])
                        else:
                            data = [issue_res.get("data", {}).get("settled", {})] if issue_res.get("data") else []
                            
                    except Exception as e:
                        logging.error(f"ဂိမ်းဒေတာရယူရာတွင် အမှား အသုံးပြုသူ {user_id} အတွက်: {e}")
                        continue
                    
                    if user_id in user_pending_bets and user_pending_bets[user_id]:
                        pending_bets_copy = user_pending_bets[user_id].copy()
                        
                        for period, (bet_type, amount) in pending_bets_copy.items():
                            settled = None
                            for item in data:
                                issue_num = item.get("issueNumber", "")
                                if str(issue_num) == str(period):
                                    settled = item
                                    break
                            
                            if settled:
                                try:
                                    number_str = str(settled.get("number", "0"))
                                    last_digit = int(number_str[-1]) if number_str else 0
                                    big_small = "B" if last_digit >= 5 else "S"
                                    
                                    is_win = (bet_type == "B" and big_small == "B") or (bet_type == "S" and big_small == "S")
                                    
                                    logging.info(f"ရလဒ်တွေ့ရှိပါပြီ အသုံးပြုသူ {user_id}, အကြိမ်ရေ {period}: နံပါတ်={number_str}, နောက်ဆုံးဂဏန်း={last_digit}, ရလဒ်={big_small}, လောင်းကြေးအမျိုးအစား={bet_type}, အနိုင်={is_win}, ပမာဏ={amount}")
                                    
                                    current_bet_index = settings.get("bet_index", 0)
                                    bet_sizes = settings.get("bet_sizes", [])
                                    sl_limit = settings.get("sl_limit")
                                    skip_betting = settings.get("skip_betting", False)
                                    consecutive_losses = settings.get("consecutive_losses", 0)
                                    original_bet_index = settings.get("original_bet_index", 0)
                                    
                                    if is_win:
                                        if amount == 0 and not skip_betting:
                                            settings["bet_index"] = 0
                                            settings["consecutive_losses"] = 0
                                            settings["skip_betting"] = False
                                            logging.info(f"အခမဲ့အနိုင်! ပြန်လည်စတင်နေပါပြီ အသုံးပြုသူ {user_id} အတွက်")
                                        
                                        elif skip_betting:
                                            new_index = original_bet_index + 1
                                            if new_index >= len(bet_sizes):
                                                new_index = len(bet_sizes) - 1
                                            settings["bet_index"] = new_index
                                            settings["consecutive_losses"] = 0
                                            settings["skip_betting"] = False
                                            logging.info(f"SL မုဒ်အနိုင်! နောက်တစ်ဆင့်သို့ရွှေ့နေပါပြီ အသုံးပြုသူ {user_id} အတွက်")
                                        
                                        elif amount > 0 and not skip_betting:
                                            settings["bet_index"] = 0
                                            settings["consecutive_losses"] = 0
                                            settings["skip_betting"] = False
                                            logging.info(f"အနိုင်! ပြန်လည်စတင်နေပါပြီ အသုံးပြုသူ {user_id} အတွက်")
                                    
                                    else:
                                        if amount == 0 and not skip_betting:
                                            settings["consecutive_losses"] += 1
                                            if current_bet_index < len(bet_sizes) - 1:
                                                settings["bet_index"] = current_bet_index + 1
                                                logging.info(f"အခမဲ့အရှုံး! နောက်တစ်ဆင့်သို့ရွှေ့နေပါပြီ အသုံးပြုသူ {user_id} အတွက်")
                                        
                                        elif amount > 0 and not skip_betting:
                                            settings["consecutive_losses"] += 1
                                            if sl_limit is not None and settings["consecutive_losses"] >= sl_limit:
                                                settings["skip_betting"] = True
                                                settings["original_bet_index"] = current_bet_index
                                                logging.info(f"SL ကန့်သတ်ချက် {sl_limit} ရောက်ရှိသွားပါပြီ! SL မုဒ်သို့ဝင်ရောက်နေပါပြီ အသုံးပြုသူ {user_id} အတွက်")
                                            elif current_bet_index < len(bet_sizes) - 1:
                                                settings["bet_index"] = current_bet_index + 1
                                                logging.info(f"အရှုံး! နောက်တစ်ဆင့်သို့ရွှေ့နေပါပြီ အသုံးပြုသူ {user_id} အတွက်")
                                        
                                        elif skip_betting:
                                            logging.info(f"SL မုဒ်အရှုံး အသုံးပြုသူ {user_id} အတွက်")
                                    
                                    if user_id not in user_stats:
                                        user_stats[user_id] = {"start_balance": 0.0, "profit": 0.0, "win_count": 0, "consecutive_wins": 0}
                                    
                                    if amount > 0:
                                        if settings.get("bank_mode") == "DEMO":
                                            if is_win:
                                                win_amount = amount * 1.96
                                                update_demo_balance(user_id, win_amount, True)
                                                user_stats[user_id]["win_count"] = user_stats[user_id].get("win_count", 0) + 1
                                                user_stats[user_id]["consecutive_wins"] = user_stats[user_id].get("consecutive_wins", 0) + 1
                                                user_stats[user_id]["profit"] += amount * 0.96
                                            else:
                                                user_stats[user_id]["consecutive_wins"] = 0
                                                user_stats[user_id]["profit"] -= amount
                                        else:
                                            if is_win:
                                                win_amount = amount * 0.96
                                                user_stats[user_id]["profit"] += win_amount
                                                user_stats[user_id]["win_count"] = user_stats[user_id].get("win_count", 0) + 1
                                                user_stats[user_id]["consecutive_wins"] = user_stats[user_id].get("consecutive_wins", 0) + 1
                                            else:
                                                user_stats[user_id]["profit"] -= amount
                                                user_stats[user_id]["consecutive_wins"] = 0
                                    elif amount == 0 and is_win:
                                        user_stats[user_id]["win_count"] = user_stats[user_id].get("win_count", 0) + 1
                                        user_stats[user_id]["consecutive_wins"] = user_stats[user_id].get("consecutive_wins", 0) + 1
                                    
                                    current_balance = await get_user_balance(session, user_id)
                                    
                                    skip_betting_status = "SL" if settings.get("skip_betting", False) else ""
                                    original_index_info = f" (ညွှန်းကိန်း {original_bet_index+1} တွင်ရှိခဲ့သည်: {bet_sizes[original_bet_index] if original_bet_index < len(bet_sizes) else 'N/A'} ကျပ်)" if settings.get("skip_betting", False) and is_win else ""
                                    
                                    if amount > 0:
                                        if is_win:
                                            result_text = (
                                                f"✅ အနိုင် + {amount * 1.96:.0f} ကျပ်{skip_betting_status}{original_index_info}\n"
                                                f"📌 {period} = {big_small} (နံပါတ်: {number_str})\n"
                                                f"💰 စာရင်း: {current_balance:,.0f} ကျပ်\n"
                                                f"📈 စုစုပေါင်းအမြတ်: {user_stats[user_id]['profit']:,.0f} ကျပ်\n"
                                                f"✅ အနိုင်အရေအတွက်: {user_stats[user_id].get('win_count', 0)}\n"
                                                f"🔄 နောက်လောင်းကြေး: {bet_sizes[settings['bet_index']] if bet_sizes else 0} ကျပ် (ညွှန်းကိန်း: {settings['bet_index']+1})\n"
                                                f"📉 ဆက်တိုက်အရှုံး: {settings.get('consecutive_losses', 0)}"
                                            )
                                        else:
                                            result_text = (
                                                f"❌ အရှုံး - {amount:.0f} ကျပ်{skip_betting_status}\n"
                                                f"📌 {period} = {big_small} (နံပါတ်: {number_str})\n"
                                                f"💰 စာရင်း: {current_balance:,.0f} ကျပ်\n"
                                                f"📉 စုစုပေါင်းအမြတ်: {user_stats[user_id]['profit']:,.0f} ကျပ်\n"
                                                f"🔄 နောက်လောင်းကြေး: {bet_sizes[settings['bet_index']] if bet_sizes else 0} ကျပ် (ညွှန်းကိန်း: {settings['bet_index']+1})\n"
                                                f"📉 ဆက်တိုက်အရှုံး: {settings.get('consecutive_losses', 0)}"
                                            )
                                    else:
                                        if is_win:
                                            result_text = (
                                                f"🎯 အခမဲ့အနိုင်{skip_betting_status}{original_index_info}\n"
                                                f"📌 {period} = {big_small} (နံပါတ်: {number_str})\n"
                                                f"💰 စာရင်း: {current_balance:,.0f} ကျပ်\n"
                                                f"📈 စုစုပေါင်းအမြတ်: {user_stats[user_id]['profit']:,.0f} ကျပ်\n"
                                                f"🔄 နောက်လောင်းကြေး: {bet_sizes[settings['bet_index']] if bet_sizes else 0} ကျပ် (ညွှန်းကိန်း: {settings['bet_index']+1})\n"
                                                f"📉 ဆက်တိုက်အရှုံး: {settings.get('consecutive_losses', 0)}"
                                            )
                                        else:
                                            result_text = (
                                                f"📌 {period} = {big_small} (နံပါတ်: {number_str}){skip_betting_status}\n"
                                                f"💰 စာရင်း: {current_balance:,.0f} ကျပ်\n"
                                                f"📈 စုစုပေါင်းအမြတ်: {user_stats[user_id]['profit']:,.0f} ကျပ်\n"
                                                f"🔄 နောက်လောင်းကြေး: {bet_sizes[settings['bet_index']] if bet_sizes else 0} ကျပ် (ညွှန်းကိန်း: {settings['bet_index']+1})\n"
                                                f"📉 ဆက်တိုက်အရှုံး: {settings.get('consecutive_losses', 0)}"
                                            )
                                    
                                    await send_message_with_retry(context.bot, user_id, result_text)
                                    
                                    target_profit = settings.get("target_profit")
                                    stop_loss = settings.get("stop_loss")
                                    if user_id in user_stats:
                                        current_profit = user_stats[user_id]["profit"]
                                        if target_profit and current_profit >= target_profit:
                                            await send_message_with_retry(context.bot, user_id, 
                                                                         f"🎉 အမြတ်ပစ်မှတ်ပြည့်သွားပါပြီ! 🎉\n"
                                                                         f"ဘော့ရပ်လိုက်ပါပြီ! အမြတ်: {current_profit:.0f} ကျပ်")
                                            settings["running"] = False
                                        elif stop_loss and current_profit <= -stop_loss:
                                            await send_message_with_retry(context.bot, user_id, 
                                                                         f"🚨 အရှုံးကန့်သတ်ချက်ထိသွားပါပြီ! 🚨\n"
                                                                         f"အရှုံး: {-current_profit:.0f} ကျပ် (ကန့်သတ်ချက်: {stop_loss:.0f} ကျပ်)\n"
                                                                         f"ဘော့ရပ်လိုက်ပါပြီ!")
                                            settings["running"] = False
                                    
                                    settings["last_result"] = big_small
                                    
                                    if user_id in user_pending_bets and period in user_pending_bets[user_id]:
                                        del user_pending_bets[user_id][period]
                                        if not user_pending_bets[user_id]:
                                            user_waiting_for_result[user_id] = False
                                    
                                    logging.info(f"ရလဒ်စီမံဆောင်ရွက်ပြီးပါပြီ အသုံးပြုသူ {user_id} အတွက်: {result_text}")
                                    
                                except Exception as e:
                                    logging.error(f"ရလဒ်စီမံဆောင်ရွက်ရာတွင် အမှား အသုံးပြုသူ {user_id}, အကြိမ်ရေ {period}: {e}")
                                    continue
                            
                            else:
                                bet_time = settings.get("bet_time", {}).get(period, time.time())
                                if time.time() - bet_time > MAX_RESULT_WAIT_TIME:
                                    logging.warning(f"ရလဒ်စောင့်ဆိုင်းချိန်လွန်သွားပါပြီ အသုံးပြုသူ {user_id}, အကြိမ်ရေ {period}")
                                    
                                    if user_id in user_pending_bets and period in user_pending_bets[user_id]:
                                        del user_pending_bets[user_id][period]
                                        if not user_pending_bets[user_id]:
                                            user_waiting_for_result[user_id] = False
                                        
                                        settings["bet_index"] = 0
                                        settings["consecutive_losses"] = 0
                                        settings["skip_betting"] = False
                                        
                                        await send_message_with_retry(context.bot, user_id, 
                                                                     f"⏰ အချိန်ကုန်သွားပါပြီ အကြိမ်ရေ {period} အတွက် ရလဒ်စောင့်ဆိုင်းရာတွင်။\n"
                                                                     f"လောင်းကြေးရှင်းလင်းပြီးပါပြီ။ လောင်းကြေးအစဉ်ကို ပြန်လည်စတင်နေပါပြီ...")
                
                except Exception as e:
                    logging.error(f"အနိုင်/အရှုံးစစ်ဆေးရေးတွင် အမှား အသုံးပြုသူ {user_id} အတွက်: {e}")
                    continue
            
            await asyncio.sleep(WIN_LOSE_CHECK_INTERVAL)
            
        except Exception as e:
            logging.error(f"အနိုင်/အရှုံးစစ်ဆေးရေးပင်မလုပ်ဆောင်ချက်အမှား: {e}")
            await asyncio.sleep(10)

async def betting_worker(user_id: int, chat_id: int, app_context: ContextTypes.DEFAULT_TYPE):
    settings = user_settings.get(user_id, {})
    session = user_sessions.get(user_id)
    if not settings or not session:
        logging.error(f"လောင်းကြေးထည့်သွင်းမှု မအောင်မြင်ပါ အသုံးပြုသူ {user_id} အတွက်: ဆက်တင်များမရှိပါ")
        await send_message_with_retry(app_context.bot, chat_id, "ကျေးဇူးပြု၍ ဦးစွာဝင်ရောက်ပါ")
        if settings:
            settings["running"] = False
        return
    
    user_stats[user_id] = {"start_balance": user_stats.get(user_id, {}).get("start_balance", 0.0), "profit": 0.0, "win_count": 0, "consecutive_wins": 0}
    settings["running"] = True
    settings["bet_time"] = {}
    settings["last_issue"] = None
    settings["consecutive_errors"] = 0
    settings["bet_index"] = 0
    settings["skip_betting"] = False
    settings["consecutive_losses"] = 0
    settings["original_bet_index"] = 0
    
    current_balance = None
    for attempt in range(MAX_BALANCE_RETRIES):
        current_balance = await get_user_balance(session, user_id)
        if current_balance is not None:
            break
        logging.warning(f"စာရင်းစစ်ဆေးမှု မအောင်မြင်ပါ အသုံးပြုသူ {user_id} အတွက်, အကြိမ် {attempt + 1}/{MAX_BALANCE_RETRIES}")
        if attempt == MAX_BALANCE_RETRIES - 1:
            logging.error(f"စာရင်းစစ်ဆေးမှု မအောင်မြင်ပါ အသုံးပြုသူ {user_id} အတွက် {MAX_BALANCE_RETRIES} ကြိမ်အထိ")
            await send_message_with_retry(app_context.bot, chat_id, "စာရင်းစစ်ဆေးမှု မအောင်မြင်ပါ။ ရပ်နားနေပါသည်...")
            settings["running"] = False
            return
        await asyncio.sleep(BALANCE_RETRY_DELAY)
    
    await send_message_with_retry(app_context.bot, chat_id, f"✅ ဘော့စတင်နေပါပြီ!\nစာရင်း: {current_balance:.2f} ကျပ်")
    logging.info(f"လောင်းကြေးထည့်သွင်းမှု စတင်နေပါပြီ အသုံးပြုသူ {user_id} အတွက်, ဆက်တင်များ: {settings}")
    
    try:
        while settings["running"]:
            try:
                if user_waiting_for_result.get(user_id, False):
                    wait_start = time.time()
                    while user_waiting_for_result.get(user_id, False) and settings["running"]:
                        if time.time() - wait_start > MAX_RESULT_WAIT_TIME:
                            logging.warning(f"အချိန်ကုန်သွားပါပြီ အသုံးပြုသူ {user_id} အတွက်")
                            user_waiting_for_result[user_id] = False
                            if user_id in user_pending_bets:
                                old_periods = list(user_pending_bets[user_id].keys())
                                for period in old_periods:
                                    del user_pending_bets[user_id][period]
                            break
                        await asyncio.sleep(1)
                    
                    if not settings["running"]:
                        break
                
                current_balance = None
                for attempt in range(MAX_BALANCE_RETRIES):
                    current_balance = await get_user_balance(session, user_id)
                    if current_balance is not None:
                        break
                    await asyncio.sleep(BALANCE_RETRY_DELAY)
                
                if current_balance is None:
                    logging.error(f"စာရင်းရယူ၍မရပါ အသုံးပြုသူ {user_id} အတွက်")
                    await send_message_with_retry(app_context.bot, chat_id, "စာရင်းစစ်ဆေး၍မရပါ။ ရပ်နားနေပါသည်...")
                    settings["running"] = False
                    break
                
                game_type = settings.get("game_type", "WINGO")
                issue_res = get_game_issue_request(session, game_type)
                
                if not isinstance(issue_res, dict) or issue_res.get("code") != 0:
                    logging.error(f"ဂိမ်းထုတ်ပြန်မှု မအောင်မြင်ပါ အသုံးပြုသူ {user_id}, ဂိမ်းအမျိုးအစား {game_type}: {issue_res}")
                    settings["consecutive_errors"] = settings.get("consecutive_errors", 0) + 1
                    if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                        logging.error(f"ဆက်တိုက်အမှားအများဆုံး ({MAX_CONSECUTIVE_ERRORS}) ရောက်ရှိသွားပါပြီ အသုံးပြုသူ {user_id} အတွက်။ ဘော့ရပ်နားနေပါသည်။")
                        await send_message_with_retry(app_context.bot, chat_id, f"ဆက်တိုက်အမှားများလွန်းပါသည် ({MAX_CONSECUTIVE_ERRORS})။ ဘော့ရပ်နားနေပါသည်။")
                        settings["running"] = False
                        break
                    await asyncio.sleep(2)
                    continue
                
                data = issue_res.get("data", {})
                current_issue = None
                draw_time = None
                
                if game_type == "TRX":
                    predraw = data.get("predraw", {})
                    current_issue = predraw.get("issueNumber")
                    draw_time = predraw.get("drawTime")
                    
                    if draw_time:
                        try:
                            draw_timestamp = int(draw_time) / 1000
                            if draw_timestamp <= time.time():
                                logging.info(f"ဖြေရှင်းပြီးသားထုတ်ပြန်မှုကို ကျော်သွားပါပြီ {current_issue}")
                                settings["last_issue"] = current_issue
                                await asyncio.sleep(1)
                                continue
                        except Exception as e:
                            logging.error(f"အချိန်စစ်ဆေးရာတွင် အမှား: {e}")
                else:
                    current_issue = data.get("issueNumber")
                
                if not current_issue:
                    logging.warning(f"တရားဝင်ထုတ်ပြန်မှုနံပါတ်မရှိပါ အသုံးပြုသူ {user_id} အတွက်")
                    await asyncio.sleep(1)
                    continue
                
                if current_issue == settings.get("last_issue"):
                    await asyncio.sleep(1)
                    continue
                
                pattern_type = settings.get("pattern_type", "sequential")
                formula_mode = settings.get("formula_mode", "straight")
                
                if pattern_type == "lottery_follow":
                    last_result = settings.get("last_result")
                    if last_result:
                        ch = last_result
                    else:
                        pattern = settings.get("pattern", "BS")
                        pidx = settings.get("pattern_index", 0) % len(pattern)
                        ch = pattern[pidx]
                elif pattern_type == "lottery_brain":
                    last_result = settings.get("last_result")
                    if last_result:
                        ch = "B" if last_result == "S" else "S"
                    else:
                        pattern = settings.get("pattern", "BS")
                        pidx = settings.get("pattern_index", 0) % len(pattern)
                        ch = pattern[pidx]
                else:
                    pattern = settings.get("pattern")
                    if not pattern:
                        logging.error(f"လောင်းကြေးအစဉ်မရှိပါ အသုံးပြုသူ {user_id} အတွက်")
                        await send_message_with_retry(app_context.bot, chat_id, "လောင်းကြေးအစဉ်မရှိပါ။ ရပ်နားနေပါသည်။")
                        settings["running"] = False
                        break
                    pidx = settings.get("pattern_index", 0) % len(pattern)
                    ch = pattern[pidx]
                
                ch = apply_formula_mode(ch, formula_mode)

                select_type = get_select_map(game_type).get(ch)
                if select_type is None:
                    logging.error(f"လောင်းကြေးအမျိုးအစား မမှန်ပါ {ch} အသုံးပြုသူ {user_id} အတွက်")
                    await send_message_with_retry(app_context.bot, chat_id, f"လောင်းကြေးအမျိုးအစား မမှန်ပါ: {ch}. ပြန်လည်ကြိုးစားနေပါသည်...")
                    settings["consecutive_errors"] += 1
                    if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                        logging.error(f"ဆက်တိုက်အမှားအများဆုံး ({MAX_CONSECUTIVE_ERRORS}) ရောက်ရှိသွားပါပြီ အသုံးပြုသူ {user_id} အတွက်။ ဘော့ရပ်နားနေပါသည်။")
                        await send_message_with_retry(app_context.bot, chat_id, f"ဆက်တိုက်အမှားများလွန်းပါသည် ({MAX_CONSECUTIVE_ERRORS})။ ဘော့ရပ်နားနေပါသည်။")
                        settings["running"] = False
                        break
                    await asyncio.sleep(2)
                    continue
                
                bet_sizes = settings.get("bet_sizes", [100])
                if not bet_sizes:
                    logging.error(f"လောင်းကြေးပမာဏများမရှိပါ အသုံးပြုသူ {user_id} အတွက်")
                    await send_message_with_retry(app_context.bot, chat_id, "လောင်းကြေးပမာဏများမရှိပါ။ ကျေးဇူးပြု၍ လောင်းကြေးအစဉ်ကို ဦးစွာသတ်မှတ်ပါ။")
                    settings["running"] = False
                    break
                
                skip_betting = settings.get("skip_betting", False)
                
                if skip_betting:
                    amount = 0
                    logging.info(f"SL မုဒ်အသက်ဝင်နေပါပြီ အသုံးပြုသူ {user_id} အတွက်, ၀ ကျပ်လောင်းနေပါသည်")
                else:
                    bet_index = settings.get("bet_index", 0)
                    if bet_index >= len(bet_sizes):
                        bet_index = len(bet_sizes) - 1
                    amount = bet_sizes[bet_index]
                
                is_free_bet = (amount == 0)
                
                if not is_free_bet and current_balance < amount:
                    logging.error(f"စာရင်းမလုံလောက်ပါ အသုံးပြုသူ {user_id} အတွက်: {current_balance} < {amount}")
                    await send_message_with_retry(app_context.bot, chat_id, f"စာရင်းမလုံလောက်ပါ!\nလက်ရှိ: {current_balance:.2f} ကျပ်\nလိုအပ်သည်: {amount:.2f} ကျပ်\nရပ်နားနေပါသည်...")
                    settings["running"] = False
                    break
                
                current_time = datetime.now().strftime('%H:%M')
                
                if formula_mode == "straight":
                    formula_indicator = " 🛞"
                elif formula_mode == "reverse":
                    formula_indicator = " 🧭"
                elif formula_mode == "back":
                    formula_indicator = " 🤑"
                else:
                    formula_indicator = ""
                
                sl_indicator = "SL" if skip_betting else ""
                
                bet_msg = (
                    f"🪷 𝐋𝐨𝐭𝐮𝐬 𝐒𝐮𝐩𝐞𝐫 𝐁𝐨𝐭 𝟔 𝐋𝐨𝐭𝐭𝐞𝐫𝐲\n\n"
                    f"🎲 လောင်းကြေး {'Big' if ch == 'B' else 'Small'} ({ch}) {amount:.0f} ကျပ်{formula_indicator}{sl_indicator}\n"
                    f"📊 လောင်းကြေးအစဉ်: {settings.get('bet_index', 0) + 1}/{len(bet_sizes)} {'🆓' if is_free_bet else '💰'}\n"
                    f"📉 ဆက်တိုက်အရှုံး: {settings.get('consecutive_losses', 0)}\n"
                    f"---------------------------\n"
                    f"{'TRX' if game_type == 'TRX' else 'WG'}   : {current_issue}\n"
                    f"အခြေအနေ: လောင်းကြေးထည့်သွင်းမှုအောင်မြင်ပါသည် {current_time}"
                )
                
                await send_message_with_retry(app_context.bot, chat_id, bet_msg)
                logging.info(f"လောင်းကြေးထည့်သွင်းနေပါပြီ အသုံးပြုသူ {user_id}, ဂိမ်းအမျိုးအစား {game_type}: {bet_msg}")
                
                if not is_free_bet:
                    bet_resp = await place_bet_request(session, current_issue, select_type, amount, game_type, user_id)
                    
                    settings["last_issue"] = current_issue
                    
                    if isinstance(bet_resp, dict) and bet_resp.get("error"):
                        logging.error(f"လောင်းကြေးအမှား အသုံးပြုသူ {user_id}, ဂိမ်းအမျိုးအစား {game_type}, အကြိမ်ရေ {current_issue}: {bet_resp.get('error')}")
                        await send_message_with_retry(app_context.bot, chat_id, f"လောင်းကြေးအမှား: {bet_resp.get('error')}. နောက်အကြိမ်တွင် ပြန်လည်ကြိုးစားနေပါသည်...")
                        settings["consecutive_errors"] += 1
                        if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                            logging.error(f"ဆက်တိုက်အမှားအများဆုံး ({MAX_CONSECUTIVE_ERRORS}) ရောက်ရှိသွားပါပြီ အသုံးပြုသူ {user_id} အတွက်။ ဘော့ရပ်နားနေပါသည်။")
                            await send_message_with_retry(app_context.bot, chat_id, f"ဆက်တိုက်အမှားများလွန်းပါသည် ({MAX_CONSECUTIVE_ERRORS})။ ဘော့ရပ်နားနေပါသည်။")
                            settings["running"] = False
                            break
                        await asyncio.sleep(5)
                        continue
                    elif isinstance(bet_resp, dict) and bet_resp.get("code") != 0:
                        error_msg = bet_resp.get("msg", "အမည်မသိအမှား")
                        logging.error(f"API အမှား အသုံးပြုသူ {user_id}, ဂိမ်းအမျိုးအစား {game_type}, အကြိမ်ရေ {current_issue}: {error_msg}")
                        await send_message_with_retry(app_context.bot, chat_id, f"API အမှား: {error_msg}. နောက်အကြိမ်တွင် ပြန်လည်ကြိုးစားနေပါသည်...")
                        if "settled" not in error_msg.lower():
                            settings["consecutive_errors"] += 1
                        if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                            logging.error(f"ဆက်တိုက်အမှားအများဆုံး ({MAX_CONSECUTIVE_ERRORS}) ရောက်ရှိသွားပါပြီ အသုံးပြုသူ {user_id} အတွက်။ ဘော့ရပ်နားနေပါသည်။")
                            await send_message_with_retry(app_context.bot, chat_id, f"ဆက်တိုက်အမှားများလွန်းပါသည် ({MAX_CONSECUTIVE_ERRORS})။ ဘော့ရပ်နားနေပါသည်။")
                            settings["running"] = False
                            break
                        await asyncio.sleep(5)
                        continue
                    settings["consecutive_errors"] = 0
                else:
                    bet_resp = {"code": 0, "msg": "အခမဲ့လောင်းကြေးထည့်သွင်းမှုအောင်မြင်ပါသည်"}
                    settings["last_issue"] = current_issue
                
                if user_id not in user_pending_bets:
                    user_pending_bets[user_id] = {}
                
                user_pending_bets[user_id][current_issue] = (ch, amount)
                
                if "bet_time" not in settings:
                    settings["bet_time"] = {}
                settings["bet_time"][current_issue] = time.time()
                
                user_waiting_for_result[user_id] = True
                settings["last_issue"] = current_issue
                
                if settings.get("pattern_type", "sequential") == "sequential":
                    settings["pattern_index"] = (settings.get("pattern_index", 0) + 1) % len(settings.get("pattern", "BS"))
                
                logging.info(f"လောင်းကြေးထည့်သွင်းပြီးပါပြီ အသုံးပြုသူ {user_id}, ဂိမ်းအမျိုးအစား {game_type}, ရလဒ်စောင့်ဆိုင်းနေပါသည် အကြိမ်ရေ {current_issue}, ပမာဏ: {amount} ကျပ်")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logging.error(f"လောင်းကြေးစက်ဝန်းတွင် အမှား အသုံးပြုသူ {user_id} အတွက်: {e}")
                settings["consecutive_errors"] = settings.get("consecutive_errors", 0) + 1
                
                if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                    settings["running"] = False
                    await send_message_with_retry(app_context.bot, chat_id, f"အမှားများလွန်းပါသည်: {str(e)}. ဘော့ရပ်နားပါသည်။")
                    break
                
                await asyncio.sleep(5)
                
    except asyncio.CancelledError:
        logging.info(f"လောင်းကြေးထည့်သွင်းမှု ဖျက်သိမ်းခံရပါသည် အသုံးပြုသူ {user_id} အတွက်")
    except Exception as e:
        logging.error(f"လောင်းကြေးထည့်သွင်းမှု အဆိုးရွားဆုံးအမှား အသုံးပြုသူ {user_id} အတွက်: {e}")
        await send_message_with_retry(app_context.bot, chat_id, f"အဆိုးရွားဆုံးအမှား: {str(e)}. ဘော့ရပ်နားပါသည်။")
    finally:
        settings["running"] = False
        user_waiting_for_result.pop(user_id, None)
        if user_id in user_pending_bets:
            user_pending_bets[user_id].clear()
        
        session = user_sessions.get(user_id)
        current_balance = await get_user_balance(session, user_id) if session else None
        balance_text = f"💰 စာရင်း: {current_balance:,.0f} ကျပ်\n" if current_balance is not None else ""
        profit_text = f"📈 စုစုပေါင်းအမြတ်: {user_stats.get(user_id, {}).get('profit', 0):,.0f} ကျပ်\n" if user_id in user_stats else ""
        
        await send_message_with_retry(app_context.bot, chat_id,
                                     f"🛑 ဘော့ရပ်နားပါပြီ!\n{balance_text}{profit_text}",
                                     reply_markup=make_main_keyboard(logged_in=True))

def make_main_keyboard(logged_in: bool = False):
    if not logged_in:
        return ReplyKeyboardMarkup([["🔐 ဝင်ရောက်မယ်"]], resize_keyboard=True, one_time_keyboard=False)
    return ReplyKeyboardMarkup(
        [
            ["🔐 ဝင်ရောက်မယ်", "✅ စတင်မယ်", "⛔ ရပ်မယ်"],
            ["🎮 ဂိမ်းရွေးမယ်", "💵 လောင်းကြေးအစဉ်"],
            ["🧠 နည်းဗျူဟာပြောင်းမယ်"],
            ["🚨 SL ကန့်သတ်ချက်", "🎯 အမြတ်ပစ်မှတ်"],
            ["⛔ အရှုံးကန့်သတ်ချက်", "💰 စာရင်းကြည့်မယ်"],
            ["🖨️ အချက်အလက်စစ်ဆေးမယ်"]
        ],
        resize_keyboard=True, one_time_keyboard=False
    )

def make_platform_keyboard():
    return ReplyKeyboardMarkup([
        ["🔴 6lottery"],
        ["🔵 Cklottery"],
        ["🟢 777bigwin"],
        ["🔙 ပင်မမီနူး"]
    ], resize_keyboard=True)

def make_strategy_keyboard():
    return ReplyKeyboardMarkup([
        ["👑 Mr King", "💎 V 1", "🎰 Lottery Father"],
        ["🤖 AI WAVE", "🤖 AI King", "🤖 AI Chat"],
        ["📈 Lottery Follow", "🧠 Lottery Brain", "⭐ KM_Enhance"],
        ["🔙 ပင်မမီနူး"]
    ], resize_keyboard=True)

async def account_balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        await send_message_with_retry(context.bot, update.effective_chat.id, "ကျေးဇူးပြု၍ ဦးစွာဝင်ရောက်ပါ", reply_markup=make_main_keyboard(logged_in=False))
        return
    
    session = user_sessions[user_id]
    user_info = user_game_info.get(user_id, {})
    settings = user_settings.get(user_id, {})
    
    balance = await get_user_balance(session, user_id)
    if balance is None:
        balance = 0.0
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    game_type = settings.get("game_type", "WINGO")
    platform = settings.get("platform", "Unknown")
    
    balance_text = (
        f"⏰ အချိန်: {current_time}\n"
        f"🎮 ဂိမ်း: {game_type}\n"
        f"💰 စာရင်း: {balance:,.2f} ကျပ်\n"
        f"🆔 ID: {user_info.get('user_id', 'N/A')}\n"
        f"🏛️ ပလက်ဖောင်း: {platform}"
    )
    
    await send_message_with_retry(context.bot, update.effective_chat.id, balance_text, reply_markup=make_main_keyboard(logged_in=True))

async def km_enhance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_settings:
        user_settings[user_id] = {}
    
    pattern = "BSSBSSBSBBSBSBSBBSBSBBSSBBSBSBBSBSBBSBBSBBBSBSSSBBBBB"
    user_settings[user_id]["pattern"] = pattern
    user_settings[user_id]["pattern_type"] = "sequential"
    
    await send_message_with_retry(context.bot, update.effective_chat.id, 
                                 f"✅ KM_Enhance နည်းဗျူဟာ သတ်မှတ်ပြီးပါပြီ:\n{pattern}",
                                 reply_markup=make_main_keyboard(logged_in=True))

async def check_user_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        await send_message_with_retry(context.bot, update.effective_chat.id, "ကျေးဇူးပြု၍ ဦးစွာဝင်ရောက်ပါ", reply_markup=make_main_keyboard(logged_in=False))
        return False
    if user_id not in user_settings:
        user_settings[user_id] = {
            "strategy": "BS_ORDER",
            "betting_strategy": "Martingale",
            "game_type": "WINGO",
            "martin_index": 0,
            "dalembert_units": 1,
            "pattern_index": 0,
            "running": False,
            "consecutive_losses": 0,
            "current_layer": 0,
            "skip_betting": False,
            "bank_mode": "REAL",
            "pattern_type": "sequential",
            "formula_mode": "straight",
            "bet_index": 0,
            "original_bet_index": 0
        }
        logging.info(f"ဆက်တင်များ စတင်သတ်မှတ်ပြီးပါပြီ အသုံးပြုသူ {user_id} အတွက်")
    return True
    
def get_strategy_by_display_name(display_name: str) -> Optional[dict]:
    cleaned_name = display_name.strip()
    
    if "Lottery Follow" in cleaned_name:
        return {"pattern_type": "lottery_follow"}
    if "Lottery Brain" in cleaned_name:
        return {"pattern_type": "lottery_brain"}
    
    reverse_map = {v: k for k, v in STRATEGY_NAMES.items()}
    
    strategy_key = reverse_map.get(cleaned_name)
    
    if strategy_key == "Mr King":
        return {"pattern_type": "sequential", "pattern": "SBSBSBBSBSBBSBBSSBSBSBBBSBBBSSSBSBSBBSBSSSBSSSBBBBSSSBSBSBBBSSSSBBBBBSBSSSBSSSBSSBBBSBSS"}
    elif strategy_key == "V 1":
        return {"pattern_type": "sequential", "pattern": "SBSSSBBBBBSSBBSSSBBSSSBSSBBBSBBSSBSSBSBSBSSSBBSBSSSSSBBBSBBSBBBSBSBBBBSBSSBBSSSBBBSSBSBSBBBBSBS"}
    elif strategy_key == "Lottery Father":
        return {"pattern_type": "sequential", "pattern": "BSBBSBSSBSSBSBBSBBSBSSBBSBSSBSBSSSSBSBBBBSSSSSSSBSSSBBSBBSBSSBSSBSBBSSSSSSSBSSSBBSSSSBSBBBBSBBSBSSBBSBSSBS"}
    elif strategy_key == "AI WAVE":
        return {"pattern_type": "sequential", "pattern": "SSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSS"}
    elif strategy_key == "AI King":
        return {"pattern_type": "sequential", "pattern": "SSBBSSSSSBSSBBSSBSSBBBBSBSS"}
    elif strategy_key == "AI Chat":
        return {"pattern_type": "sequential", "pattern": "BSBBSBBSBSSSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSSBSBSBSBSBSBBSSBSSBBSBSSBBSBBSSBBBSSSSSBBSBBSSBSSBBBSBSSSBSBBSSBSBBBSBBBBSSSSSBBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSSSSSBBBBBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSBBBBSSSSSBBBBSSBSBBBSBBSSBSSBBSBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSBBSSBSSBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBBBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSBSBSSBSSBSBBBSSBBBBBSBBSSSSBSBBSBBSBSSBBSSSBSBBBSBBBBSSBBBBBSBBSSSBBBSBBBSBBBSBBBSBBSSBSSSBBSSBBSSBBBSBBBSBBBSBBBBBSSSSSSBBSSSSBSBSSSSBBSSSSBBSSSSSBSSSSBSBBBSBBBSBBSSBBBSBBBSBBBSBBBSBBSBSBSBSBSBSBBSSBSSBBSBSSBBSBBSSBBBSSSSSBBSBBSSBSSBBBSBSSSBSBBSSBSBBBSBBBBSSSSSBBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSSSSSBBBBBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSBBBBSSSSSBBBBSSBSBBBSBBSSBSSBBSBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSBBSSBSSBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBBBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSB"}
    elif strategy_key == "KM_Enhance":
        return {"pattern_type": "sequential", "pattern": "BSSBSSBSBBSBSBSBBSBSBBSSBBSBSBBSBSBBSBBSBBBSBSSSBBBBB"}
    elif strategy_key == "Manual":
        return {"pattern_type": "sequential", "pattern": "BS"}
        
    return None

async def cmd_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_settings:
        user_settings[user_id] = {
            "strategy": "BS_ORDER",
            "betting_strategy": "Martingale",
            "game_type": "WINGO",
            "martin_index": 0,
            "dalembert_units": 1,
            "pattern_index": 0,
            "running": False,
            "consecutive_losses": 0,
            "current_layer": 0,
            "skip_betting": False,
            "bank_mode": "REAL",
            "pattern_type": "sequential",
            "formula_mode": "straight",
            "bet_index": 0,
            "original_bet_index": 0
        }
        logging.info(f"ဆက်တင်များ စတင်သတ်မှတ်ပြီးပါပြီ အသုံးပြုသူ {user_id} အတွက်")
    logged_in = user_id in user_sessions
    
    welcome_message = (
        "🌟 မင်္ဂလာပါ ကြိုဆိုပါတယ်\n\n"
        "🪷 K RAW ALL LOTTERY AUTO BET BOT\n\n"
        "🎰 LOTTERY (ကြီး,ငယ်) အလိုအလျောက်လောင်းသည့်ဘော့\n\n"
        "────────────────────\n"
        "📌 အကြီးအကဲ 🖇️ @RAW1113\n"
        "🎰 အကောက်ဖွင့်ရန်လင့်\n"
        "🖇️ https://www.777bigwingame.vip/#/register?invitationCode=52651649234\n"
        "🖇 http://www.cklottery.tv/#/register?invitationCode=52585635882\n"
        "🖇 https://www.6win999.com/#/register?invitationCode=665221114876\n"
        "────────────────────\n\n"
        "စတင်ရန် 🔐 ဝင်ရောက်မယ် ကိုနှိပ်ပါ!"
    )
    
    await send_message_with_retry(context.bot, update.effective_chat.id, welcome_message, reply_markup=make_main_keyboard(logged_in))
    if not hasattr(context.application, 'win_lose_task') or context.application.win_lose_task.done():
        context.application.win_lose_task = asyncio.create_task(win_lose_checker(context.application))

async def cmd_allow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await send_message_with_retry(context.bot, update.effective_chat.id, "အကြီးအကဲမှသာလျှင် အသုံးပြုနိုင်သည်!")
        return
    if not context.args or not context.args[0].isdigit():
        await send_message_with_retry(context.bot, update.effective_chat.id, "အသုံးပြုပုံ: /allow {ဂိမ်းအိုင်ဒီ}")
        return
    ingame_id = int(context.args[0])
    # Store mapping from ingame_id to telegram user id
    # We need to find which telegram user has this ingame_id
    # For simplicity, we'll store in allowed_user_ids with key as ingame_id
    allowed_user_ids[str(ingame_id)] = {"ingame_id": ingame_id, "allowed_by": ADMIN_ID, "time": time.time()}
    save_allowed_users()
    await send_message_with_retry(context.bot, update.effective_chat.id, f"✅ ဂိမ်းအိုင်ဒီ {ingame_id} အား ခွင့်ပြုလိုက်ပါပြီ")

async def cmd_remove_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await send_message_with_retry(context.bot, update.effective_chat.id, "အကြီးအကဲမှသာလျှင် အသုံးပြုနိုင်သည်!")
        return
    if not context.args or not context.args[0].isdigit():
        await send_message_with_retry(context.bot, update.effective_chat.id, "အသုံးပြုပုံ: /remove {ဂိမ်းအိုင်ဒီ}")
        return
    ingame_id = int(context.args[0])
    if str(ingame_id) not in allowed_user_ids:
        await send_message_with_retry(context.bot, update.effective_chat.id, f"ဂိမ်းအိုင်ဒီ {ingame_id} ကို ရှာမတွေ့ပါ")
    else:
        del allowed_user_ids[str(ingame_id)]
        save_allowed_users()
        await send_message_with_retry(context.bot, update.effective_chat.id, f"❌ ဂိမ်းအိုင်ဒီ {ingame_id} အား ဖယ်ရှားလိုက်ပါပြီ")

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text
    text = normalize_text(raw_text)
    logging.info(f"ထည့်သွင်းမှု အသုံးပြုသူ {user_id}: {raw_text}")
    logging.info(f"ပုံမှန်ဖြစ်အောင်ပြုလုပ်ထားသော ထည့်သွင်းမှု အသုံးပြုသူ {user_id}: {text}")
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    logging.info(f"ခွဲထုတ်ထားသောစာကြောင်းများ အသုံးပြုသူ {user_id} (အရေအတွက်: {len(lines)}): {lines}")
    logging.info(f"လက်ရှိအခြေအနေ အသုံးပြုသူ {user_id} အတွက်: {user_state.get(user_id, 'None')}")

    if text == "🔐 ဝင်ရောက်မယ်":
        if user_id not in user_sessions:
            user_state[user_id] = {"state": "WAIT_PLATFORM"}
            await send_message_with_retry(context.bot, update.effective_chat.id, "🟢 သင့်ပလက်ဖောင်းကို ရွေးချယ်ပါ", reply_markup=make_platform_keyboard())
            return
        else:
            await send_message_with_retry(context.bot, update.effective_chat.id, "သင်သည် ဝင်ရောက်ပြီးသားဖြစ်သည်!", reply_markup=make_main_keyboard(logged_in=True))
            return
    
    if user_state.get(user_id, {}).get("state") == "WAIT_PLATFORM":
        # Find which platform was selected
        selected_platform = None
        for platform_key in PLATFORM_URLS.keys():
            if PLATFORM_NAMES[platform_key] == text:
                selected_platform = platform_key
                break
        
        if selected_platform:
            user_temp[user_id] = {"platform": selected_platform, "base_url": PLATFORM_URLS[selected_platform]}
            user_state[user_id] = {"state": "WAIT_PHONE"}
            await send_message_with_retry(context.bot, update.effective_chat.id, "ဖုန်းနံပါတ် သို့မဟုတ် အီးမေးလ် ထည့်သွင်းပါ:")
            return
        elif text == "🔙 ပင်မမီနူး":
            user_state.pop(user_id, None)
            user_temp.pop(user_id, None)
            await send_message_with_retry(context.bot, update.effective_chat.id, "ပင်မမီနူး", reply_markup=make_main_keyboard(logged_in=False))
            return
        else:
            await send_message_with_retry(context.bot, update.effective_chat.id, "ကျေးဇူးပြု၍ တရားဝင်ပလက်ဖောင်းကို ရွေးချယ်ပါ။", reply_markup=make_platform_keyboard())
            return
    
    if user_state.get(user_id, {}).get("state") == "WAIT_PHONE":
        if user_temp.get(user_id) and user_temp[user_id].get("platform"):
            user_temp[user_id]["phone"] = text
            user_state[user_id] = {"state": "WAIT_PASS"}
            await send_message_with_retry(context.bot, update.effective_chat.id, "စကားဝှက်ထည့်သွင်းပါ:")
            return
        else:
            await send_message_with_retry(context.bot, update.effective_chat.id, "ပလက်ဖောင်းမရွေးချယ်ရသေးပါ။ ကျေးဇူးပြု၍ အစမှပြန်စပါ။", reply_markup=make_main_keyboard(logged_in=False))
            user_state.pop(user_id, None)
            user_temp.pop(user_id, None)
            return
    
    if user_state.get(user_id, {}).get("state") == "WAIT_PASS":
        if user_temp.get(user_id) and user_temp[user_id].get("phone") and user_temp[user_id].get("platform"):
            phone = user_temp[user_id]["phone"]
            password = text
            base_url = user_temp[user_id]["base_url"]
            platform = user_temp[user_id]["platform"]
            logging.info(f"ဝင်ရောက်ရန် ကြိုးစားနေပါသည် အသုံးပြုသူ {user_id} အတွက် ပလက်ဖောင်း {platform} ပေါ်တွင်")
            await send_message_with_retry(context.bot, update.effective_chat.id, "ဝင်ရောက်နေပါသည်...")
            
            res, session = login_request(phone, password, base_url)
            if session:
                user_info = await get_user_info(session, user_id)
                if user_info and user_info.get("user_id"):
                    game_user_id = user_info.get("user_id")
                    # Check authorization for all platforms
                    if str(game_user_id) not in allowed_user_ids:
                        logging.warning(f"ခွင့်ပြုချက်မရှိသော ဝင်ရောက်မှု အသုံးပြုသူ {user_id}, ဂိမ်းအိုင်ဒီ {game_user_id} ပလက်ဖောင်း {platform} ပေါ်တွင်")
                        session.close()
                        await send_message_with_retry(context.bot, update.effective_chat.id, 
                            f"🚫 ဝင်ခွင့် မရှိသေးပါ\n\n"
                            f"သင်၏ ID: {game_user_id}\n\n"
                            f"ဝင်ခွင့်ရရန် @RAW1113 ကိုဆက်သွယ်ပါ ။\n\n"
                            f"🔴6lottery\n🔵cklottery\n🟢777bigwin", 
                            reply_markup=make_main_keyboard(logged_in=False))
                        return
                    user_sessions[user_id] = session
                    user_game_info[user_id] = user_info
                    if user_id not in user_settings:
                        user_settings[user_id] = {}
                    user_settings[user_id]["platform"] = platform
                    user_settings[user_id]["base_url"] = base_url
                    balance = await get_balance(session, user_id)
                    user_stats[user_id] = {"start_balance": float(balance or 0), "profit": 0.0, "win_count": 0, "consecutive_wins": 0}
                    if "game_type" not in user_settings[user_id]:
                        user_settings[user_id].update({
                            "strategy": "BS_ORDER",
                            "betting_strategy": "Martingale",
                            "game_type": "WINGO",
                            "martin_index": 0,
                            "dalembert_units": 1,
                            "pattern_index": 0,
                            "running": False,
                            "consecutive_losses": 0,
                            "current_layer": 0,
                            "skip_betting": False,
                            "bank_mode": "REAL",
                            "pattern_type": "sequential",
                            "formula_mode": "straight",
                            "bet_index": 0,
                            "original_bet_index": 0
                        })
                    balance_display = balance if balance is not None else 0.0
                    await send_message_with_retry(context.bot, update.effective_chat.id, 
                                                 f"✅ ဝင်ရောက်မှုအောင်မြင်ပါသည်!\nပလက်ဖောင်း: {platform}\n🆔 : {user_info['user_id']}\n💰 စာရင်း: {balance_display:.2f} ကျပ်", 
                                                 reply_markup=make_main_keyboard(logged_in=True))
                else:
                    await send_message_with_retry(context.bot, update.effective_chat.id, "ဝင်ရောက်မှုမအောင်မြင်ပါ: အသုံးပြုသူအချက်အလက်ရယူ၍မရပါ", reply_markup=make_main_keyboard(logged_in=False))
            else:
                msg = res.get("msg", "ဝင်ရောက်မှုမအောင်မြင်ပါ")
                await send_message_with_retry(context.bot, update.effective_chat.id, f"ဝင်ရောက်မှုအမှား: {msg}", reply_markup=make_main_keyboard(logged_in=False))
            user_state.pop(user_id, None)
            user_temp.pop(user_id, None)
            return
        else:
            await send_message_with_retry(context.bot, update.effective_chat.id, "ဝင်ရောက်မှုသက်တမ်းကုန်သွားပါပြီ။ ကျေးဇူးပြု၍ အစမှပြန်စပါ။", reply_markup=make_main_keyboard(logged_in=False))
            user_state.pop(user_id, None)
            user_temp.pop(user_id, None)
            return
    
    if not await check_user_authorized(update, context):
        return
    
    if text == "💰 စာရင်းကြည့်မယ်":
        await account_balance_handler(update, context)
        return
    
    if text == "⭐ KM_Enhance":
        await km_enhance_handler(update, context)
        return
    
    if text in ["👑 Mr King", "💎 V 1", "🎰 Lottery Father", "🤖 AI WAVE", "🤖 AI King", "🤖 AI Chat", "📈 Lottery Follow", "🧠 Lottery Brain", "⭐ KM_Enhance"]:
        if text == "👑 Mr King":
            user_settings[user_id]["pattern"] = "SBSBSBBSBSBBSBBSSBSBSBBBSBBBSSSBSBSBBSBSSSBSSSBBBBSSSBSBSBBBSSSSBBBBBSBSSSBSSSBSSBBBSBSS"
            user_settings[user_id]["pattern_type"] = "sequential"
            await send_message_with_retry(context.bot, update.effective_chat.id, 
                                        "✅ နည်းဗျူဟာ သတ်မှတ်ပြီးပါပြီ: 👑 Mr King",
                                        reply_markup=make_main_keyboard(logged_in=True))
        elif text == "💎 V 1":
            user_settings[user_id]["pattern"] = "SBSSSBBBBBSSBBSSSBBSSSBSSBBBSBBSSBSSBSBSBSSSBBSBSSSSSBBBSBBSBBBSBSBBBBSBSSBBSSSBBBSSBSBSBBBBSBS"
            user_settings[user_id]["pattern_type"] = "sequential"
            await send_message_with_retry(context.bot, update.effective_chat.id, 
                                        "✅ နည်းဗျူဟာ သတ်မှတ်ပြီးပါပြီ: 💎 V 1",
                                        reply_markup=make_main_keyboard(logged_in=True))
        elif text == "🎰 Lottery Father":
            user_settings[user_id]["pattern"] = "BSBBSBSSBSSBSBBSBBSBSSBBSBSSBSBSSSSBSBBBBSSSSSSSBSSSBBSBBSBSSBSSBSBBSSSSSSSBSSSBBSSSSBSBBBBSBBSBSSBBSBSSBS"
            user_settings[user_id]["pattern_type"] = "sequential"
            await send_message_with_retry(context.bot, update.effective_chat.id, 
                                        "✅ နည်းဗျူဟာ သတ်မှတ်ပြီးပါပြီ: 🎰 Lottery Father",
                                        reply_markup=make_main_keyboard(logged_in=True))
        elif text == "🤖 AI WAVE":
            user_settings[user_id]["pattern"] = "SSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSS"
            user_settings[user_id]["pattern_type"] = "sequential"
            await send_message_with_retry(context.bot, update.effective_chat.id, 
                                        "✅ နည်းဗျူဟာ သတ်မှတ်ပြီးပါပြီ: 🤖 AI WAVE",
                                        reply_markup=make_main_keyboard(logged_in=True))
        elif text == "🤖 AI King":
            user_settings[user_id]["pattern"] = "SSBBSSSSSBSSBBSSBSSBBBBSBSS"
            user_settings[user_id]["pattern_type"] = "sequential"
            await send_message_with_retry(context.bot, update.effective_chat.id, 
                                        "✅ နည်းဗျူဟာ သတ်မှတ်ပြီးပါပြီ: 🤖 AI King",
                                        reply_markup=make_main_keyboard(logged_in=True))
        elif text == "🤖 AI Chat":
            user_settings[user_id]["pattern"] = "BSBBSBBSBSSSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSSBSSBSBBSSBBBSBSSSBSSSSBBSSSSSBSSBBBBSBSSBSBSBSBSBSBBSSBSSBBSBSSBBSBBSSBBBSSSSSBBSBBSSBSSBBBSBSSSBSBBSSBSBBBSBBBBSSSSSBBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSSSSSBBBBBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSBBBBSSSSSBBBBSSBSBBBSBBSSBSSBBSBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSBBSSBSSBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBBBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSBSBSSBSSBSBBBSSBBBBBSBBSSSSBSBBSBBSBSSBBSSSBSBBBSBBBBSSBBBBBSBBSSSBBBSBBBSBBBSBBBSBBSSBSSSBBSSBBSSBBBSBBBSBBBSBBBBBSSSSSSBBSSSSBSBSSSSBBSSSSBBSSSSSBSSSSBSBBBSBBBSBBSSBBBSBBBSBBBSBBBSBBSBSBSBSBSBSBBSSBSSBBSBSSBBSBBSSBBBSSSSSBBSBBSSBSSBBBSBSSSBSBBSSBSBBBSBBBBSSSSSBBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSSSSSBBBBBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSBBBBSSSSSBBBBSSBSBBBSBBSSBSSBBSBSBSSSBSBBBBBSBSSSBSBSSBSSBBSBBBSBBSSBSSBSBBBSBSSSBBBBBSSSSSBSSSSSBBBBBBSSSSSBBBBBSBSBSBSBSBBBBSSSSSBSSBBSBBSSBBSBSSSBSBBSBBSSBSSB"
            user_settings[user_id]["pattern_type"] = "sequential"
            await send_message_with_retry(context.bot, update.effective_chat.id, 
                                        "✅ နည်းဗျူဟာ သတ်မှတ်ပြီးပါပြီ: 🤖 AI Chat",
                                        reply_markup=make_main_keyboard(logged_in=True))
        elif text == "📈 Lottery Follow":
            user_settings[user_id]["pattern_type"] = "lottery_follow"
            await send_message_with_retry(context.bot, update.effective_chat.id, 
                                        "✅ နည်းဗျူဟာ သတ်မှတ်ပြီးပါပြီ: 📈 Lottery Follow\nနောက်ဆုံးရလဒ်ကို လိုက်ပါမည်",
                                        reply_markup=make_main_keyboard(logged_in=True))
        elif text == "🧠 Lottery Brain":
            user_settings[user_id]["pattern_type"] = "lottery_brain"
            await send_message_with_retry(context.bot, update.effective_chat.id, 
                                        "✅ နည်းဗျူဟာ သတ်မှတ်ပြီးပါပြီ: 🧠 Lottery Brain\nနောက်ဆုံးရလဒ်နှင့် ဆန့်ကျင်ဘက် လောင်းမည်",
                                        reply_markup=make_main_keyboard(logged_in=True))
        elif text == "⭐ KM_Enhance":
            await km_enhance_handler(update, context)
            return
        return
    
    if text == "🔙 ပင်မမီနူး":
        await send_message_with_retry(context.bot, update.effective_chat.id, "ပင်မမီနူး", reply_markup=make_main_keyboard(logged_in=True))
        return
    
    if text == "🖨️ အချက်အလက်စစ်ဆေးမယ်":
        logging.info(f"အသုံးပြုသူ {user_id} က အချက်အလက်စစ်ဆေးမယ်ကို နှိပ်လိုက်ပါပြီ")
        
        session = user_sessions.get(user_id)
        user_info = await get_user_info(session, user_id) if session else None
        settings = user_settings.get(user_id, {})
        balance = await get_user_balance(session, user_id) if session else None
        bet_sizes = settings.get("bet_sizes", [])
        profit_target = settings.get("target_profit")
        stop_loss = settings.get("stop_loss")
        sl_limit = settings.get("sl_limit")
        betting_strategy = settings.get("betting_strategy", "Martingale")
        game_type = settings.get("game_type", "WINGO")
        formula_mode = settings.get("formula_mode", "straight")
        
        strategy_display = get_strategy_display_name(settings)
        
        if formula_mode == "straight":
            formula_display = "🛞 ပုံမှန်"
        elif formula_mode == "reverse":
            formula_display = "🧭 ပြောင်းပြန်"
        elif formula_mode == "back":
            formula_display = "🤑 BACK"
        else:
            formula_display = formula_mode
        
        stats = user_stats.get(user_id, {"profit": 0.0, "win_count": 0})
        
        info_text = (
            f"🆔 အသုံးပြုသူအိုင်ဒီ: {user_info.get('user_id', 'N/A') if user_info else 'N/A'}\n"
            f"💰 စာရင်း: {balance:.2f} ကျပ်\n"
            f"🎮 ဂိမ်း: {game_type}\n"
            f"🧠 နည်းဗျူဟာ: {strategy_display}\n"
            f"🎲 ဖော်မြူလာမုဒ်: {formula_display}\n"
            f"💵 လောင်းကြေးနည်းဗျူဟာ: {betting_strategy}\n"
            f"💸 လောင်းကြေးအစဉ်: {', '.join(map(str, bet_sizes)) if bet_sizes else ''}\n"
            f"📊 လက်ရှိလောင်းကြေးညွှန်းကိန်း: {settings.get('bet_index', 0) + 1}/{len(bet_sizes) if bet_sizes else 0}\n"
            f"🎯 အမြတ်ပစ်မှတ်: {f'{profit_target:.2f} ကျပ်' if isinstance(profit_target, (int, float)) else ''}\n"
            f"⛔ အရှုံးကန့်သတ်ချက်: {f'{stop_loss:.2f} ကျပ်' if isinstance(stop_loss, (int, float)) else ''}\n"
            f"🚨 SL ကန့်သတ်ချက်: {sl_limit if sl_limit is not None else ''}\n"
            f"📈 စုစုပေါင်းအမြတ်: {stats['profit']:.2f} ကျပ်\n"
            f"✅ အနိုင်အရေအတွက်: {stats.get('win_count', 0)}\n"
            f"📉 ဆက်တိုက်အရှုံး: {settings.get('consecutive_losses', 0)}\n"
            f"🚀 လုပ်ဆောင်နေသလား: {'ဟုတ်ကဲ့' if settings.get('running', False) else 'မဟုတ်ပါ'}"
        )
        await send_message_with_retry(context.bot, update.effective_chat.id, info_text, reply_markup=make_main_keyboard(logged_in=True))
        return
    
    try:
        if user_state.get(user_id, {}).get("state") == "INPUT_BET_SIZES":
            bet_sizes = [int(s) for s in lines[1:] if s.isdigit()]
            if not bet_sizes:
                raise ValueError("တရားဝင်ဂဏန်းများမရှိပါ")
            user_settings[user_id]["bet_sizes"] = bet_sizes
            user_settings[user_id]["bet_index"] = 0
            user_settings[user_id]["original_bet_index"] = 0
            await send_message_with_retry(context.bot, update.effective_chat.id, 
                                         f"💵 လောင်းကြေးအစဉ် သတ်မှတ်ပြီးပါပြီ: {', '.join(map(str, bet_sizes))} ကျပ်\n\n"
                                         f"အနိုင် = ပထမပမာဏသို့ပြန်သွားမည်\n"
                                         f"အရှုံး = နောက်တစ်ဆင့်သို့ရွှေ့မည်\n"
                                         f"SL ကန့်သတ်ချက်ရောက်လျှင် = အနိုင်ရသည်အထိ ၀ ကျပ်လောင်းမည်၊ ထို့နောက် နောက်တစ်ဆင့်သို့ရွှေ့မည်",
                                         reply_markup=make_main_keyboard(logged_in=True))
            user_state.pop(user_id, None)
        
        elif user_state.get(user_id, {}).get("state") == "INPUT_BET_ORDER":
            pattern = lines[1] if len(lines) >= 2 else text
            if all(c in "BS" for c in pattern.upper()) and pattern:
                user_settings[user_id]["pattern"] = pattern.upper()
                user_settings[user_id]["pattern_type"] = "sequential"
                await send_message_with_retry(context.bot, update.effective_chat.id, f"📝 ကိုယ်တိုင်လောင်းကြေးအစဉ် သတ်မှတ်ပြီးပါပြီ: {pattern.upper()}", reply_markup=make_main_keyboard(logged_in=True))
                user_state.pop(user_id, None)
            else:
                await send_message_with_retry(context.bot, update.effective_chat.id, "လောင်းကြေးအစဉ် မမှန်ကန်ပါ။ B သို့မဟုတ် S ကိုသာ သုံးပါ:\nBet_Order\nBSBBSSBSBBS", reply_markup=make_main_keyboard(logged_in=True))
        
        elif user_state.get(user_id, {}).get("state") == "INPUT_PROFIT_TARGET":
            target = float(lines[1] if len(lines) >= 2 else text)
            if target <= 0:
                raise ValueError
            user_settings[user_id]["target_profit"] = target
            await send_message_with_retry(context.bot, update.effective_chat.id, f"🎯 အမြတ်ပစ်မှတ် သတ်မှတ်ပြီးပါပြီ: {target:.2f} ကျပ်", reply_markup=make_main_keyboard(logged_in=True))
            user_state.pop(user_id, None)
        
        elif user_state.get(user_id, {}).get("state") == "INPUT_STOP_LIMIT":
            stop_loss = float(lines[1] if len(lines) >= 2 else text)
            if stop_loss <= 0:
                raise ValueError
            user_settings[user_id]["stop_loss"] = stop_loss
            await send_message_with_retry(context.bot, update.effective_chat.id, f"⛔ အရှုံးကန့်သတ်ချက် သတ်မှတ်ပြီးပါပြီ: {stop_loss:.2f} ကျပ်", reply_markup=make_main_keyboard(logged_in=True))
            user_state.pop(user_id, None)
        
        elif user_state.get(user_id, {}).get("state") == "INPUT_SL_LIMIT":
            sl_limit = int(lines[1] if len(lines) >= 2 else text)
            if sl_limit < 0:
                raise ValueError("SL သည် အနုတ်မဟုတ်သောကိန်းပြည့်ဖြစ်ရပါမည်")
            user_settings[user_id]["sl_limit"] = sl_limit if sl_limit > 0 else None
            user_settings[user_id]["consecutive_losses"] = 0
            user_settings[user_id]["skip_betting"] = False
            await send_message_with_retry(context.bot, update.effective_chat.id, 
                                         f"🚨 SL ကန့်သတ်ချက် သတ်မှတ်ပြီးပါပြီ: {sl_limit if sl_limit is not None else ''} ဆက်တိုက်အရှုံး\n\n"
                                         f"{sl_limit} ဆက်တိုက်အရှုံးရောက်သောအခါ:\n"
                                         f"- အနိုင်ရသည်အထိ ၀ ကျပ်လောင်းမည်\n"
                                         f"- ထို့နောက် နောက်တစ်ဆင့်သို့ရွှေ့မည် (မူလသို့မဟုတ်ပါ)",
                                         reply_markup=make_main_keyboard(logged_in=True))
            user_state.pop(user_id, None)
        
        elif user_state.get(user_id, {}).get("state") == "INPUT_GAME_TYPE":
            game_type = text.upper()
            if game_type in ["WINGO", "TRX"]:
                user_settings[user_id]["game_type"] = game_type
                await send_message_with_retry(context.bot, update.effective_chat.id, f"🎮 ဂိမ်း သတ်မှတ်ပြီးပါပြီ: {game_type}", reply_markup=make_main_keyboard(logged_in=True))
                user_state.pop(user_id, None)
            else:
                await send_message_with_retry(context.bot, update.effective_chat.id, "ဂိမ်းအမျိုးအစား မမှန်ကန်ပါ။ WINGO သို့မဟုတ် TRX ထည့်ပါ", reply_markup=make_main_keyboard(logged_in=True))
        
        else:
            if text == "💵 လောင်းကြေးအစဉ်":
                user_state[user_id] = {"state": "INPUT_BET_SIZES"}
                await send_message_with_retry(context.bot, update.effective_chat.id, 
                                             "လောင်းကြေးအစဉ် ထည့်သွင်းပါ:\nBet_Sequence\n0\n10\n20\n30\n\n"
                                             "ဥပမာ: 0,10,20,30\n(0 = အခမဲ့လောင်းကြေး, SL မုဒ်အတွက် အသုံးပြုသည်)",
                                             reply_markup=make_main_keyboard(logged_in=True))
            
            elif text == "🧠 နည်းဗျူဟာပြောင်းမယ်":
                await send_message_with_retry(context.bot, update.effective_chat.id, "နည်းဗျူဟာရွေးချယ်ပါ:", reply_markup=make_strategy_keyboard())
            
            elif text == "✅ စတင်မယ်":
                settings = user_settings.get(user_id, {})
                logging.info(f"စတင်ရန် အမိန့် အသုံးပြုသူ {user_id} အတွက်, ဆက်တင်များ: {settings}")
                if not settings.get("bet_sizes"):
                    await send_message_with_retry(context.bot, update.effective_chat.id, "ဦးစွာ 💵 လောင်းကြေးအစဉ် သတ်မှတ်ပါ!", reply_markup=make_main_keyboard(logged_in=True))
                    return
                if settings.get("pattern_type", "sequential") == "sequential" and not settings.get("pattern"):
                    await send_message_with_retry(context.bot, update.effective_chat.id, "ဦးစွာ 📝 ကိုယ်တိုင်လောင်းကြေးအစဉ် သတ်မှတ်ပါ!", reply_markup=make_main_keyboard(logged_in=True))
                    return
                if settings.get("running"):
                    await send_message_with_retry(context.bot, update.effective_chat.id, "ဘော့ လုပ်ဆောင်နေပြီးသားဖြစ်သည်!", reply_markup=make_main_keyboard(logged_in=True))
                    return
                settings["martin_index"] = 0
                settings["dalembert_units"] = 1
                settings["pattern_index"] = 0
                settings["consecutive_losses"] = 0
                settings["skip_betting"] = False
                settings["running"] = True
                settings["consecutive_errors"] = 0
                settings["bet_index"] = 0
                settings["original_bet_index"] = 0
                user_waiting_for_result[user_id] = False
                task = asyncio.create_task(betting_worker(user_id, update.effective_chat.id, context))
                settings["task"] = task
            
            elif text == "⛔ ရပ်မယ်":
                settings = user_settings.get(user_id, {})
                if not settings.get("running"):
                    await send_message_with_retry(context.bot, update.effective_chat.id, "ဘော့ လုပ်ဆောင်နေခြင်းမရှိပါ!", reply_markup=make_main_keyboard(logged_in=True))
                    return
                settings["running"] = False
                if settings.get("task"):
                    settings["task"].cancel()
                    settings["task"] = None
                user_waiting_for_result.pop(user_id, None)
                session = user_sessions.get(user_id)
                current_balance = await get_user_balance(session, user_id) if session else None
                balance_text = f"စာရင်း: {current_balance:.2f} ကျပ်\n" if current_balance is not None else ""
                await send_message_with_retry(context.bot, update.effective_chat.id, f"ဘော့ရပ်နားပါပြီ!\n{balance_text}", reply_markup=make_main_keyboard(logged_in=True))
            
            elif text == "🎮 ဂိမ်းရွေးမယ်":
                user_state[user_id] = {"state": "INPUT_GAME_TYPE"}
                await send_message_with_retry(context.bot, update.effective_chat.id, "WINGO သို့မဟုတ် TRX", reply_markup=make_main_keyboard(logged_in=True))
            
            elif text == "🎯 အမြတ်ပစ်မှတ်":
                user_state[user_id] = {"state": "INPUT_PROFIT_TARGET"}
                await send_message_with_retry(context.bot, update.effective_chat.id, "အမြတ်ပစ်မှတ် ထည့်သွင်းပါ\nProfit_Target\n100000", reply_markup=make_main_keyboard(logged_in=True))
            
            elif text == "⛔ အရှုံးကန့်သတ်ချက်":
                user_state[user_id] = {"state": "INPUT_STOP_LIMIT"}
                await send_message_with_retry(context.bot, update.effective_chat.id, "သင်၏ SL ပစ်မှတ် ထည့်သွင်းပါ\n\nဥပမာ: 100000", reply_markup=make_main_keyboard(logged_in=True))
            
            elif text == "🚨 SL ကန့်သတ်ချက်":
                user_state[user_id] = {"state": "INPUT_SL_LIMIT"}
                await send_message_with_retry(context.bot, update.effective_chat.id, 
                                             "SL ထည့်သွင်းပါ:\nBet_SL\n3\n(0 သည် ပိတ်ရန်)\n\n"
                                             "ဥပမာ: 2 ဆိုလျှင် ဆက်တိုက် 2 ကြိမ်အရှုံးရပြီးနောက်၊\n"
                                             "ဘော့သည် အနိုင်ရသည်အထိ ၀ ကျပ်လောင်းမည်၊ ထို့နောက် နောက်တစ်ဆင့်သို့ရွှေ့မည်",
                                             reply_markup=make_main_keyboard(logged_in=True))
            
            else:
                await send_message_with_retry(context.bot, update.effective_chat.id, "မမှန်ကန်သော အမိန့် သို့မဟုတ် ထည့်သွင်းမှု။", reply_markup=make_main_keyboard(logged_in=True))
            
    except ValueError as e:
        await send_message_with_retry(context.bot, update.effective_chat.id, f"ထည့်သွင်းမှု မမှန်ကန်ပါ: {str(e)}", reply_markup=make_main_keyboard(logged_in=True))
    except Exception as e:
        logging.error(f"ထည့်သွင်းမှုကိုင်တွယ်ရာတွင် အမှား အသုံးပြုသူ {user_id} အတွက်: {str(e)}")
        await send_message_with_retry(context.bot, update.effective_chat.id, f"အမှား: {str(e)}", reply_markup=make_main_keyboard(logged_in=True))

def main():
    load_allowed_users()
    
    # Start Flask server in a separate thread for Render
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start_handler))
    application.add_handler(CommandHandler("allow", cmd_allow_handler))
    application.add_handler(CommandHandler("remove", cmd_remove_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
