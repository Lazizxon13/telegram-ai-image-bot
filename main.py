import telebot
from openai import OpenAI
import os
import base64
import sqlite3
from io import BytesIO
from flask import Flask, request

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found")

# ===== INIT =====
bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

# ===== DATABASE =====
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    used INTEGER DEFAULT 0,
    paid_remaining INTEGER DEFAULT 0
)
""")
conn.commit()

FREE_LIMIT = 1
ADMIN_ID = 601900410  # O'zingizning Telegram ID

# ===== LIMIT FUNCTION =====
def check_limit(user_id):
    cursor.execute(
        "SELECT used, paid_remaining FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO users (user_id, used, paid_remaining) VALUES (?, ?, ?)",
            (user_id, 1, 0)
        )
        conn.commit()
        return True, 0

    used, paid_remaining = row

    # Premium ishlatish
    if paid_remaining > 0:
        cursor.execute(
            "UPDATE users SET paid_remaining=? WHERE user_id=?",
            (paid_remaining - 1, user_id)
        )
        conn.commit()
        return True, paid_remaining - 1

    # Free limit
    if used >= FREE_LIMIT:
        return False, 0

    cursor.execute(
        "UPDATE users SET used=? WHERE user_id=?",
        (used + 1, user_id)
    )
    conn.commit()
    return True, 0


# ===== ADD PREMIUM =====
def add_paid(user_id, amount):
    cursor.execute(
        "SELECT user_id FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO users (user_id, used, paid_remaining) VALUES (?, ?, ?)",
            (user_id, 0, amount)
        )
    else:
        cursor.execute(
            "UPDATE users SET paid_remaining = paid_remaining + ? WHERE user_id=?",
            (amount, user_id)
        )
    conn.commit()


# ===== START =====
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(
        message,
        "🎨 Salom!\n\n"
        "1 ta bepul rasm beriladi.\n"
        "Premium olish uchun admin bilan bog'laning."
    )
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

@bot.message_handler(commands=['buy'])
def buy_menu(message):
    markup = InlineKeyboardMarkup()

    btn1 = InlineKeyboardButton("💎 5 rasm — 10 000 so‘m", callback_data="buy_5")
    btn2 = InlineKeyboardButton("💎 20 rasm — 30 000 so‘m", callback_data="buy_20")

    markup.add(btn1)
    markup.add(btn2)

    bot.send_message(
        message.chat.id,
        "💎 Premium paketni tanlang:",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):

    user_id = call.from_user.id

    if call.data == "buy_5":
        text = (
            "💎 5 ta rasm — 10 000 so‘m\n\n"
            "💳 Karta: 8600 0366 8782 8503\n"
            "👤 Ism: ORIBJON\n\n"
            "To‘lov qilgandan so‘ng chekni shu yerga yuboring.\n"
            f"🆔 Sizning ID: {https://t.me/ORIFFFFFFFFFF}"
        )

    elif call.data == "buy_20":
        text = (
            "💎 20 ta rasm — 30 000 so‘m\n\n"
            "💳 Karta: 8600 1234 5678 9012\n"
            "👤 Ism: ORIBJON\n\n"
            "To‘lov qilgandan so‘ng chekni shu yerga yuboring.\n"
            f"🆔 Sizning ID: {user_id}"
        )

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text)

# ===== ADMIN STATS =====
@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(used) FROM users")
    total_used = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(paid_remaining) FROM users")
    total_paid = cursor.fetchone()[0] or 0

    bot.reply_to(
        message,
        f"""📊 STATISTIKA

👥 Jami user: {total_users}
🖼 Bepul ishlatilgan: {total_used}
💎 Qolgan premium: {total_paid}
"""
    )

# ===== IMAGE =====
@bot.message_handler(content_types=['text'])
def generate_image(message):
    user_id = message.from_user.id

    allowed, remaining = check_limit(user_id)

   if not allowed:
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton("💎 Premium olish", callback_data="open_buy")
    markup.add(btn)

    bot.send_message(
        message.chat.id,
        "❌ Limit tugadi.\nPremium olish uchun tugmani bosing 👇",
        reply_markup=markup
    )
    return
@bot.callback_query_handler(func=lambda call: call.data == "open_buy")
def open_buy_menu(call):
    markup = InlineKeyboardMarkup()

    btn1 = InlineKeyboardButton("💎 5 rasm — 10 000 so‘m", callback_data="buy_5")
    btn2 = InlineKeyboardButton("💎 20 rasm — 30 000 so‘m", callback_data="buy_20")

    markup.add(btn1)
    markup.add(btn2)

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "💎 Premium paketni tanlang:",
        reply_markup=markup
    )
    prompt = message.text

    enhanced_prompt = f"""
    Ultra high quality, professional photography,
    cinematic lighting, detailed, sharp focus.
    {prompt}
    """

    try:
        response = client.images.generate(
            model="gpt-image-1",
            prompt=enhanced_prompt,
            size="1024x1024"
        )

        image_base64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        caption = f"✨ Premium qoldiq: {remaining}" if remaining > 0 else ""

        bot.send_photo(
            message.chat.id,
            BytesIO(image_bytes),
            caption=caption
        )

    except Exception as e:
        print("OPENAI ERROR:", e)
        bot.reply_to(message, "⚠️ Rasm yaratishda xatolik.")

# ===== WEBHOOK =====
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        json_string = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return "ERROR", 500

@app.route("/")
def home():
    return "Bot ishlayapti", 200

@app.route("/health")
def health():
    return "OK", 200
