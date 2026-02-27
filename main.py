import telebot
from openai import OpenAI
import os
import base64
from io import BytesIO
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_KEY)

app = Flask(__name__)

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "Salom! Menga rasm tavsifini yuboring 🎨")

@bot.message_handler(content_types=['text'])
def generate_image(message):
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

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=os.getenv("WEBHOOK_URL") + "/" + BOT_TOKEN)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
