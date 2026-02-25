import os
import base64
import sqlite3
from io import BytesIO
from flask import Flask, request
import telebot
from openai import OpenAI

# ===== ENV VARIABLES =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# ===== INIT =====
bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_KEY)
app = Flask(__name__)

# ===== DATABASE SETUP =====
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    used INTEGER DEFAULT 0
)
""")
conn.commit()

FREE_LIMIT = 2

# ===== LIMIT CHECK FUNCTION =====
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
        return True, FREE_LIMIT - 1

    used, paid_remaining = row

    # Agar pullik balans bo‘lsa
    if paid_remaining > 0:
        cursor.execute(
            "UPDATE users SET paid_remaining=? WHERE user_id=?",
            (paid_remaining - 1, user_id)
        )
        conn.commit()
        return True, paid_remaining - 1

    # Bepul limit tekshiruv
    if used >= FREE_LIMIT:
        return False, 0

    cursor.execute(
        "UPDATE users SET used=? WHERE user_id=?",
        (used + 1, user_id)
    )
    conn.commit()

    return True, FREE_LIMIT - (used + 1)
# ===== STYLE PROMPTS =====
STYLES = {
    "anime": "Anime style, vibrant colors, detailed illustration, 4k, studio quality",
    "realistic": "Ultra realistic photography, cinematic lighting, sharp focus, professional camera, 4k",
    "logo": "Modern minimal logo design, vector style, clean background, branding, high resolution",
    "3d": "3D render, octane render, hyper detailed, dramatic lighting, ultra hd"
}

user_styles = {}

# ===== START COMMAND =====
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(
        message,
        "🎨 Salom!\n\n"
        "Menga rasm tavsifini yuboring.\n\n"
        "Style komandalar:\n"
        "/anime\n"
        "/realistic\n"
        "/logo\n"
        "/3d\n\n"
        "Sizda 5 ta bepul rasm limiti bor."
    )

# ===== STYLE COMMANDS =====
@bot.message_handler(commands=['anime','realistic','logo','3d'])
def set_style(message):
    style = message.text.replace("/", "")
    user_styles[message.chat.id] = style
    bot.reply_to(message, f"✅ {style.upper()} style tanlandi. Endi tavsif yuboring.")

# ===== IMAGE GENERATION =====
@bot.message_handler(content_types=['text'])
def generate_image(message):
    user_id = message.from_user.id

    allowed, remaining = check_limit(user_id)

    if not allowed:
        bot.reply_to(
            message,
            "❌ Bepul limit tugadi.\nPremium olish uchun admin bilan bog'laning."
        )
        return

    style = user_styles.get(message.chat.id)
    base_prompt = message.text

    if style in STYLES:
        final_prompt = STYLES[style] + ". " + base_prompt
    else:
        final_prompt = "Ultra high quality, detailed, professional lighting. " + base_prompt

    try:
        response = client.images.generate(
            model="gpt-image-1",
            prompt=final_prompt,
           size="512x512"
        )

        image_base64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        bot.send_photo(
            message.chat.id,
            BytesIO(image_bytes),
            caption=f"✨ Qolgan bepul limit: {remaining}"
        )

    except Exception as e:
        bot.reply_to(message, "⚠️ Rasm yaratishda xatolik yuz berdi.")
        print(e)

# ===== WEBHOOK ROUTE =====
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

# ===== START SERVER =====
@app.route("/")
def home():
    return "Bot is running", 200

