import telebot
from openai import OpenAI
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_KEY)

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

    image_url = response.data[0].url
    bot.send_photo(message.chat.id, image_url)

bot.infinity_polling()
