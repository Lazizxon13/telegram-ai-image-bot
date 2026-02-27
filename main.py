import telebot
from openai import OpenAI
import os
import base64
import sqlite3
from io import BytesIO
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

# ===== DATABASE =====
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    used INTEGER DEFAULT 0
)
""")
conn.commit()

FREE_LIMIT = 1

# ===== LIMIT FUNCTION =====
def check_limit(user_id):
    cursor.execute("SELECT used FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if row is None:
        cursor.execute("INSERT INTO users (user_id, used) VALUES (?, ?)", (user_id, 1))
        conn.commit()
        return True

    used = row[0]

    if used >= FREE_LIMIT:
        return False

    cursor.execute("UPDATE users SET used=? WHERE user_id=?", (used + 1, user_id))
    conn.commit()
    return True

# ===== START =====
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "Salom! 1 ta bepul rasm beriladi 🎨")

# ===== IMAGE =====
@bot.message_handler(content_types=['text'])
def generate_image(message):
    user_id = message.from_user.id

    if not check_limit(user_id):
        bot.reply_to(message, "❌ Bepul limit tugadi.")
        return

    prompt = message.text

    enhanced_prompt = f"""
    Ultra high quality, professional photography,
    cinematic lighting, detailed, sharp focus, 4k resolution.
    {prompt}
    """

    response = client.images.generate(
        model="gpt-image-1",
        prompt=enhanced_prompt,
        size="1024x1024"
    )

    image_base64 = response.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    bot.send_photo(message.chat.id, BytesIO(image_bytes))

# ===== WEBHOOK =====
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "OK", 200
