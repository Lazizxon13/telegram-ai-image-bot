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
    raise ValueError("BOT_TOKEN topilmadi. .env faylini tekshiring.")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY topilmadi.")

# ===== SETTINGS =====
FREE_LIMIT = 1
ADMIN_ID = 601900410
CHANNEL_USERNAME = "@GreenleafRishton"   # 🔥 To'g'rilandi: API ishlashi uchun @username formatiga o'tkazildi

# ===== INIT =====
bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

# ===== DATABASE HELPER =====
# 🔥 Flask'da "database is locked" xatosini oldini olish uchun har ulanishda yopilib-ochiladigan funksiya
def get_db_connection():
    return sqlite3.connect("users.db", check_same_thread=False)

# Bazani boshlang'ich sozlash
with get_db_connection() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        used INTEGER DEFAULT 0,
        paid_remaining INTEGER DEFAULT 0,
        invited_by INTEGER DEFAULT NULL
    )
    """)
    conn.commit()

# ===== CHANNEL CHECK =====
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Obunani tekshirishda xato: {e}")
        return False

# ===== LIMIT CHECK =====
def check_limit(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT used, paid_remaining FROM users WHERE user_id=?", (user_id,))
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

# ===== ADMIN COMMAND (Yangi: Adminlar premium qo'shishi uchun) =====
@bot.message_handler(commands=['add_premium'])
def add_premium_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    args = message.text.split()
    if len(args) != 3:
        bot.reply_to(message, "Foydalanish: /add_premium <user_id> <miqdor>")
        return
        
    try:
        target_id = int(args[1])
        amount = int(args[2])
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE user_id=?", (target_id,))
            if cursor.fetchone() is None:
                cursor.execute(
                    "INSERT INTO users (user_id, used, paid_remaining) VALUES (?, ?, ?)",
                    (target_id, 0, amount)
                )
            else:
                cursor.execute(
                    "UPDATE users SET paid_remaining = paid_remaining + ? WHERE user_id=?",
                    (amount, target_id)
                )
            conn.commit()
            
        bot.reply_to(message, f"✅ Foydalanuvchi {target_id} hisobiga {amount} ta premium rasm qo'shildi.")
        try:
            bot.send_message(target_id, f"🎉 Admin tomonidan sizga {amount} ta premium rasm taqdim etildi!")
        except:
            pass
    except Exception as e:
        bot.reply_to(message, f"Xatolik yuz berdi: {e}")

# ===== START =====
@bot.message_handler(commands=['start'])
def start_message(message):
    args = message.text.split()
    user_id = message.from_user.id

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        row = cursor.fetchone()

        if row is None:
            invited_by = None
            if len(args) > 1:
                try:
                    invited_by = int(args[1])
                except:
                    invited_by = None

            cursor.execute(
                "INSERT INTO users (user_id, used, paid_remaining, invited_by) VALUES (?, ?, ?, ?)",
                (user_id, 0, 0, invited_by)
            )
            conn.commit()

            if invited_by and invited_by != user_id:
                cursor.execute(
                    "UPDATE users SET paid_remaining = paid_remaining + 1 WHERE user_id=?",
                    (invited_by,)
                )
                conn.commit()
                try:
                    bot.send_message(
                        invited_by,
                        "🎉 Referal havolangiz orqali do'stingiz qo'shildi! 1 ta bonus rasm oldingiz."
                    )
                except:
                    pass

    bot_username = bot.get_me().username
    bot.reply_to(
        message,
        f"🎨 Salom!\n\n"
        f"Sizga {FREE_LIMIT} ta bepul rasm yaratish imkoniyati beriladi.\n\n"
        f"🔗 Do'stlaringizni taklif qilib premium oling. Referal havolangiz:\n"
        f"https://t.me/{bot_username}?start={user_id}"
    )

# ===== IMAGE GENERATION =====
@bot.message_handler(content_types=['text'])
def generate_image(message):
    # 🔥 Komandalar kelganda adashib API ga so'rov ketmasligi uchun
    if message.text.startswith('/'):
        return

    user_id = message.from_user.id

    if not check_subscription(user_id):
        markup = InlineKeyboardMarkup()
        btn1 = InlineKeyboardButton(
            "📢 Kanalga a’zo bo‘lish",
            url="https://t.me/GreenleafRishton" # Bu yerda URL qoladi, bu tugma uchun
        )
        btn2 = InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
        markup.add(btn1, btn2)

        bot.send_message(
            message.chat.id,
            "❗ Botdan foydalanish uchun kanalimizga a’zo bo‘ling.",
            reply_markup=markup
        )
        return

    allowed, remaining = check_limit(user_id)

    if not allowed:
        bot.send_message(message.chat.id, "❌ Bepul limit tugadi. Do'stlaringizni taklif qilib premium limit oling.")
        return

    prompt = message.text
    wait_msg = bot.send_message(message.chat.id, "⏳ Rasm yaratilmoqda, 15-20 soniya kutishingiz mumkin...")

    try:
        # 🔥 To'g'rilangan OpenAI API qismi
        response = client.images.generate(
            model="dall-e-3", # Haqiqiy mavjud model 
            prompt=prompt,
            size="1024x1024",
            response_format="b64_json" # 🔥 Base64 formatida kutish buyrug'i
        )

        image_base64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        caption = f"💎 Qolgan premium: {remaining}" if remaining > 0 else ""

        bot.delete_message(message.chat.id, wait_msg.message_id) # Kutish xabarini o'chirish
        bot.send_photo(
            message.chat.id,
            BytesIO(image_bytes),
            caption=caption
        )

    except Exception as e:
        print(f"Rasm yaratish xatosi: {e}")
        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.reply_to(message, "⚠️ Xatolik yuz berdi. Balki so'rovingizda taqiqlangan so'zlar bordir (DALL-E xavfsizlik filtri).")

# ===== RECHECK SUB =====
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def recheck_subscription(call):
    user_id = call.from_user.id

    if check_subscription(user_id):
        bot.answer_callback_query(call.id, "✅ A’zolik tasdiqlandi!")
        bot.send_message(call.message.chat.id, "🎉 Endi botga rasm chizish uchun matn yozishingiz mumkin!")
    else:
        bot.answer_callback_query(call.id, "❌ Hali kanalga a’zo emassiz.", show_alert=True)

# ===== WEBHOOK & FLASK =====
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "Bot muvaffaqiyatli ishlamoqda!", 200

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    # Eslatma: Serverda ishlash uchun Webhookni Telegramga ulash kerak bo'ladi.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
