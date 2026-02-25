import os
import base64
from io import BytesIO
from flask import Flask, request
import telebot
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

if not OPENAI_KEY:
    raise ValueError("OPENAI_KEY not found")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_KEY)
app = Flask(__name__)

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "🎨 Matn yuboring, rasm yarataman.")

@bot.message_handler(content_types=['text'])
def generate_image(message):
    prompt = message.text

    try:
response = client.images.generate(
    model="gpt-image-1",
    prompt=prompt,
    size="1024x1024"
)
        image_base64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        bot.send_photo(
            message.chat.id,
            BytesIO(image_bytes)
        )

    except Exception as e:
        bot.reply_to(message, "⚠️ Rasm yaratishda xatolik.")
        print(e)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "OK", 200

@app.route("/health")
def health():
    return "OK", 200
