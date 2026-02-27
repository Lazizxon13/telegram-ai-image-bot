import telebot
from openai import OpenAI
import os
import base64
import sqlite3
from io import BytesIO
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found")

# ===== SETTINGS =====
FREE_LIMIT = 1
ADMIN_ID = 601900410
CHANNEL_USERNAME = "@oribjon_ai"   # 🔥 O'Z KANALINGNI YOZ

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

# ===== CHANNEL CHECK =====
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ===== LIMIT CHECK =====
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

    if paid_remaining > 0:
        cursor.execute(
            "UPDATE users SET paid_remaining=? WHERE user_id=?",
            (paid_remaining - 1, user_id)
        )
        conn.commit()
        return True, paid_remaining - 1

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
        "🎨 Salom!\n\n1 ta bepul rasm beriladi."
    )

# ===== IMAGE =====
@bot.message_handler(content_types=['text'])
def generate_image(message):

    user_id = message.from_user.id

    # 🔥 KANAL MAJBURIY
    if not check_subscription(user_id):

        markup = InlineKeyboardMarkup()
        btn1 = InlineKeyboardButton(
            "📢 Kanalga a’zo bo‘lish",
            url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}"
        )
        btn2 = InlineKeyboardButton(
            "✅ Tekshirish",
            callback_data="check_sub"
        )

        markup.add(btn1)
        markup.add(btn2)

        bot.send_message(
            message.chat.id,
            "❗ Botdan foydalanish uchun kanalga a’zo bo‘ling.",
            reply_markup=markup
        )
        return

    allowed, remaining = check_limit(user_id)

    if not allowed:
        bot.send_message(
            message.chat.id,
            "❌ Limit tugadi. Premium oling."
        )
        return

    prompt = message.text

    try:
        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )

        image_base64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        caption = ""
        if remaining > 0:
            caption = f"💎 Qolgan premium: {remaining}"

        bot.send_photo(
            message.chat.id,
            BytesIO(image_bytes),
            caption=caption
        )

    except Exception as e:
        print(e)
        bot.reply_to(message, "⚠️ Xatolik yuz berdi.")

# ===== RECHECK SUB =====
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def recheck_subscription(call):

    user_id = call.from_user.id

    if check_subscription(user_id):
        bot.answer_callback_query(call.id, "✅ A’zo tasdiqlandi!")
        bot.send_message(
            call.message.chat.id,
            "🎉 Endi botdan foydalanishingiz mumkin!"
        )
    else:
        bot.answer_callback_query(
            call.id,
            "❌ Hali kanalga a’zo emassiz.",
            show_alert=True
        )

# ===== WEBHOOK =====
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "Bot ishlayapti", 200

@app.route("/health")
def health():
    return "OK", 200
