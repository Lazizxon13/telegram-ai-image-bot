import telebot
from openai import OpenAI
import os
import base64
from io import BytesIO
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_KEY)

app = Flask(__name__)

# ===== USER LIMIT SYSTEM =====
user_limits = {}
FREE_LIMIT = 5

def check_limit(user_id):
    if user_id not in user_limits:
        user_limits[user_id] = 0
    
    if user_limits[user_id] >= FREE_LIMIT:
        return False
    
    user_limits[user_id] += 1
    return True

# ===== STYLE PROMPTS =====
STYLES = {
    "anime": "Anime style, vibrant colors, studio ghibli quality, detailed illustration, 4k",
    "realistic": "Ultra realistic photography, cinematic lighting, sharp focus, 4k, professional camera",
    "logo": "Modern minimal logo design, vector style, clean background, branding, high resolution",
    "3d": "3D render, octane render, hyper detailed, dramatic lighting, ultra hd"
}

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message,
        "Salom! 🎨\n\n"
        "Menga rasm tavsifi yuboring.\n\n"
        "Style komandalar:\n"
        "/anime\n"
        "/realistic\n"
        "/logo\n"
        "/3d\n\n"
        "Sizda 5 ta bepul rasm limiti bor."
    )

@bot.message_handler(commands=['anime','realistic','logo','3d'])
def set_style(message):
    style = message.text.replace("/", "")
    bot.send_message(message.chat.id, f"✅ {style.upper()} style tanlandi.\nEndi tavsif yuboring.")
    bot.user_style = getattr(bot, "user_style", {})
    bot.user_style[message.chat.id] = style

@bot.message_handler(content_types=['text'])
def generate_image(message):
    user_id = message.from_user.id
    
    if not check_limit(user_id):
        bot.reply_to(message,
            "❌ Bepul limit tugadi.\n"
            "Premium olish uchun admin bilan bog'laning."
        )
        return

    style = None
    if hasattr(bot, "user_style") and message.chat.id in bot.user_style:
        style = bot.user_style[message.chat.id]

    base_prompt = message.text
    
    if style and style in STYLES:
        enhanced_prompt = STYLES[style] + ". " + base_prompt
    else:
        enhanced_prompt = "Ultra high quality, detailed, professional lighting. " + base_prompt

    response = client.images.generate(
        model="gpt-image-1",
        prompt=enhanced_prompt,
        size="1024x1024"
    )

    image_base64 = response.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    remaining = FREE_LIMIT - user_limits[user_id]

    bot.send_photo(
        message.chat.id,
        BytesIO(image_bytes),
        caption=f"✨ Qolgan bepul limit: {remaining}"
    )

# ===== WEBHOOK =====
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + "/" + BOT_TOKEN)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
