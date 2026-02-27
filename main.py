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

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("BOT_TOKEN yoki OPENAI_API_KEY topilmadi. .env faylini tekshiring.")

# ===== SETTINGS =====
FREE_LIMIT = 1
ADMIN_ID = 601900410
CHANNEL_USERNAME = "@GreenleafRishton" # API ishlashi uchun @ formatida
CHANNEL_LINK = "https://t.me/GreenleafRishton" # Tugmalar uchun havola

# ===== INIT =====
bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

# ===== DATABASE HELPER =====
def get_db_connection():
    return sqlite3.connect("users.db", check_same_thread=False)

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

# ===== ADMIN COMMAND =====
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
            bot.send_message(target_id, f"🎉 Admin tomonidan sizga {amount} ta premium rasm taqdim etildi! Endi rasm chizdirishingiz mumkin.")
        except:
            pass
    except Exception as e:
        bot.reply_to(message, f"Xatolik yuz berdi: {e}")

# ===== START COMMAND =====
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
                    pass

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

    try:
        bot_username = bot.get_me().username
    except:
        bot_username = "bot_username"

    bot.reply_to(
        message,
        f"🎨 Salom!\n\n"
        f"Sizga {FREE_LIMIT} ta bepul rasm yaratish imkoniyati berildi.\n\n"
        f"🎁 **Yana bepul limit kerakmi?**\n"
        f"Do'stlaringizni taklif qiling va har bir do'stingiz uchun 1 tadan bonus rasm oling.\n"
        f"🔗 Referal havolangiz:\n"
        f"https://t.me/{bot_username}?start={user_id}\n\n"
        f"💎 **Kutishni xohlamaysizmi?**\n"
        f"Pullik paketlarni ko'rish uchun /premium buyrug'ini yuboring."
    )

# ===== PREMIUM & BUY COMMANDS =====
@bot.message_handler(commands=['premium', 'buy'])
def buy_premium(message):
    markup = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("💎 5 rasm — 10 000 so'm", callback_data="buy_5")
    btn2 = InlineKeyboardButton("💎 20 rasm — 30 000 so'm", callback_data="buy_20")
    
    markup.add(btn1)
    markup.add(btn2)
    
    bot.send_message(
        message.chat.id, 
        "💎 Premium paketni tanlang:", 
        reply_markup=markup
    )

# ===== CALLBACK QUERIES (Tugmalar bosilganda) =====
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id

    # Obunani tekshirish tugmasi
    if call.data == "check_sub":
        if check_subscription(user_id):
            bot.answer_callback_query(call.id, "✅ A’zolik tasdiqlandi!")
            bot.send_message(call.message.chat.id, "🎉 Endi botga rasm chizish uchun matn yozishingiz mumkin!")
        else:
            bot.answer_callback_query(call.id, "❌ Hali kanalga a’zo emassiz.", show_alert=True)

    # To'lov tugmalari
    elif call.data == "buy_5":
        text = (
            "💎 5 ta rasm — 10 000 so'm\n\n"
            "💳 Karta: 8600 0366 8782 8503\n"
            "👤 Ism: ORIBJON\n\n"
            "To'lov qilgandan so'ng chekni (skrinshotni) shu yerga yuboring.\n"
            f"🆔 Sizning ID: {user_id}"
        )
        bot.send_message(call.message.chat.id, text)
        bot.answer_callback_query(call.id)

    elif call.data == "buy_20":
        text = (
            "💎 20 ta rasm — 30 000 so'm\n\n"
            "💳 Karta: 8600 0366 8782 8503\n"
            "👤 Ism: ORIBJON\n\n"
            "To'lov qilgandan so'ng chekni (skrinshotni) shu yerga yuboring.\n"
            f"🆔 Sizning ID: {user_id}"
        )
        bot.send_message(call.message.chat.id, text)
        bot.answer_callback_query(call.id)
# ===== CHEK FORWARD (Yangi versiya - Tugmalar bilan) =====
@bot.message_handler(content_types=['photo'])
def forward_check(message):
    user_id = message.from_user.id
    username = message.from_user.username

    caption = (
        f"💳 Yangi to‘lov cheki!\n\n"
        f"👤 User ID: {user_id}\n"
        f"📛 Username: @{username if username else 'yo‘q'}"
    )

    markup = InlineKeyboardMarkup()
    btn5 = InlineKeyboardButton("✅ 5 ta qo'shish", callback_data=f"admin_add_5_{user_id}")
    btn20 = InlineKeyboardButton("✅ 20 ta qo'shish", callback_data=f"admin_add_20_{user_id}")
    btn_reject = InlineKeyboardButton("❌ Rad etish", callback_data=f"admin_reject_{user_id}")
    
    markup.add(btn5, btn20)
    markup.add(btn_reject)

    bot.send_photo(
        ADMIN_ID, 
        message.photo[-1].file_id, 
        caption=caption, 
        reply_markup=markup
    )

    bot.reply_to(
        message,
        "✅ Chek yuborildi. Admin tasdiqlagach, bot sizga xabar beradi."
    )

# ===== ADMIN CALLBACK (Tasdiqlash yoki Rad etish) =====
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_check_handler(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Siz admin emassiz!", show_alert=True)
        return

    data = call.data.split("_")
    action = data[1]
    
    if action == "add":
        amount = int(data[2])
        target_id = int(data[3])
        
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
        
        bot.edit_message_caption(
            f"✅ {target_id} foydalanuvchiga {amount} ta limit qo'shildi.", 
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id
        )
        
        try:
            bot.send_message(target_id, f"🎉 To'lov tasdiqlandi! Hisobingizga {amount} ta premium rasm qo'shildi. Boshlash uchun matn yozing.")
        except:
            pass

    elif action == "reject":
        target_id = int(data[2])
        
        bot.edit_message_caption(
            f"❌ {target_id} foydalanuvchining cheki rad etildi.", 
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id
        )
        
        try:
            bot.send_message(target_id, "❌ Kechirasiz, to'lov chekingiz tasdiqlanmadi. Iltimos, qaytadan urinib ko'ring yoki admin bilan bog'laning.")
        except:
            pass
        
    bot.answer_callback_query(call.id)
# ===== IMAGE GENERATION =====
@bot.message_handler(content_types=['text'])
def generate_image(message):
    if message.text.startswith('/'):
        return

    user_id = message.from_user.id

    if not check_subscription(user_id):
        markup = InlineKeyboardMarkup()
        btn1 = InlineKeyboardButton("📢 Kanalga a’zo bo‘lish", url=CHANNEL_LINK)
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
        bot.send_message(
            message.chat.id, 
            "❌ Limitingiz tugadi.\n\n"
            "Do'stlaringizni taklif qilib bepul rasm oling (Havola /start buyrug'ida) yoki "
            "darhol rasm chizdirish uchun /premium orqali paket sotib oling."
        )
        return

    prompt = message.text
    wait_msg = bot.send_message(message.chat.id, "⏳ Rasm yaratilmoqda, biroz kuting...")

    try:
        response = client.images.generate(
            model="dall-e-3", 
            prompt=prompt,
            size="1024x1024",
            response_format="b64_json"
        )

        image_base64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        caption = f"💎 Qolgan premium limit: {remaining}" if remaining > 0 else ""

        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.send_photo(
            message.chat.id,
            BytesIO(image_bytes),
            caption=caption
        )

    except Exception as e:
        print(f"Rasm yaratish xatosi: {e}")
        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.reply_to(message, "⚠️ Xatolik yuz berdi. Iltimos, boshqa so'z bilan qayta urinib ko'ring.")

# ===== WEBHOOK & FLASK =====
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "Bot ishlayapti!", 200

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
