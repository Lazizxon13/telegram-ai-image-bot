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
ADMIN_ID = 601900410


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
        "Premium olish uchun /buy ni bosing."
    )


# ===== BUY MENU =====
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


# ===== BUY CALLBACK =====
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):

    user_id = call.from_user.id

    if call.data == "buy_5":
        text = (
            "💎 5 ta rasm — 10 000 so‘m\n\n"
            "💳 Karta: 8600 0366 8782 8503\n"
            "👤 Ism: ORIBJON\n\n"
            "To‘lovdan so‘ng chekni yuboring.\n"
            f"🆔 Sizning ID: {user_id}"
        )

    elif call.data == "buy_20":
        text = (
            "💎 20 ta rasm — 30 000 so‘m\n\n"
            "💳 Karta: 8600 0366 8782 8503\n"
            "👤 Ism: ORIBJON\n\n"
            "To‘lovdan so‘ng chekni yuboring.\n"
            f"🆔 Sizning ID: {user_id}"
        )

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text)


# ===== IMAGE GENERATION =====
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

        # 👇 Premium qoldiqni ko‘rsatish
        caption_text = ""

        if remaining > 0:
            caption_text = f"✨ Rasm tayyor!\n💎 Qolgan premium: {remaining} ta"

        bot.send_photo(
            message.chat.id,
            BytesIO(image_bytes),
            caption=caption_text
        )

    except Exception as e:
        print("OPENAI ERROR:", e)
        bot.reply_to(message, "⚠️ Rasm yaratishda xatolik.")


# ===== OPEN BUY BUTTON =====
@bot.callback_query_handler(func=lambda call: call.data == "open_buy")
def open_buy_menu(call):
    bot.answer_callback_query(call.id)
    buy_menu(call.message)

# ===== CHEK FORWARD + ADMIN BUTTON =====
@bot.message_handler(content_types=['photo', 'document'])
def forward_check(message):

    user_id = message.from_user.id
    username = message.from_user.username

    markup = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton(
        "✅ 5 rasm berish",
        callback_data=f"approve_5_{user_id}"
    )
    btn2 = InlineKeyboardButton(
        "❌ Bekor qilish",
        callback_data=f"reject_{user_id}"
    )

    markup.add(btn1)
    markup.add(btn2)

    # Admin ga forward
    bot.forward_message(
        ADMIN_ID,
        message.chat.id,
        message.message_id
    )

    bot.send_message(
        ADMIN_ID,
        f"💳 Yangi to‘lov!\n\n"
        f"👤 ID: {user_id}\n"
        f"📛 Username: @{username if username else 'yo‘q'}",
        reply_markup=markup
    )

    bot.reply_to(
        message,
        "✅ Chek yuborildi. Admin tasdiqlaydi."
    )
    # ===== ADMIN APPROVE HANDLER =====
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def admin_approve(call):

    if call.from_user.id != ADMIN_ID:
        return

    data = call.data.split("_")

    if data[0] == "approve":
        amount = int(data[1])
        user_id = int(data[2])

        add_paid(user_id, amount)

        bot.send_message(
            user_id,
            f"🎉 To‘lov tasdiqlandi!\n💎 {amount} ta premium rasm qo‘shildi!"
        )

        bot.edit_message_text(
            "✅ Tasdiqlandi va premium qo‘shildi.",
            call.message.chat.id,
            call.message.message_id
        )

    elif data[0] == "reject":
        user_id = int(data[1])

        bot.send_message(
            user_id,
            "❌ To‘lov tasdiqlanmadi. Admin bilan bog‘laning."
        )

        bot.edit_message_text(
            "❌ To‘lov bekor qilindi.",
            call.message.chat.id,
            call.message.message_id
        )

    bot.answer_callback_query(call.id)
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
