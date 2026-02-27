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

# ===== ADMIN ADD =====
@bot.message_handler(commands=['add'])
def admin_add(message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Format: /add user_id amount")
        return

    user_id = int(parts[1])
    amount = int(parts[2])

    add_paid(user_id, amount)
    bot.reply_to(message, f"{amount} ta premium qo‘shildi.")

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
        bot.reply_to(message, "❌ Limit tugadi. Premium oling.")
        return

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
