import os
import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import replicate
import random

# ================= TOKENS =================
BOT_TOKEN = "8770225032:AAHGtOVcJOuyMOGihCgm0Ml1AuEeNUm9PO8"
REPLICATE_TOKEN = "r8_4kTS1AMd066YAy8cDtBBZrGQBABeTR14ZgCQ1"
ADMIN_ID = 6394219796

bot = telebot.TeleBot(BOT_TOKEN)
client = replicate.Client(api_token=REPLICATE_TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    phone TEXT,
    joined TEXT,
    photos INT DEFAULT 0,
    processed INT DEFAULT 0,
    banned_until TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT,
    action TEXT,
    time TEXT
)
""")

conn.commit()

# ================= LOG =================
def log(uid, action):
    cursor.execute("INSERT INTO logs(user_id, action, time) VALUES(?,?,?)",
                   (uid, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

# ================= BAN =================
def is_banned(user):
    if user and user[5]:
        until = datetime.strptime(user[5], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < until:
            return True, until
    return False, None

def ban_user(uid, minutes):
    until = datetime.now() + timedelta(minutes=minutes)
    cursor.execute("UPDATE users SET banned_until=? WHERE id=?",
                   (until.strftime("%Y-%m-%d %H:%M:%S"), uid))
    conn.commit()

# ================= START =================
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    user = cursor.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    if not user:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton("📱 Telefon yuborish", request_contact=True))
        bot.send_message(uid, "📱 Telefon yuboring", reply_markup=kb)
    else:
        menu(uid)

# ================= CONTACT =================
@bot.message_handler(content_types=['contact'])
def contact(m):
    uid = m.from_user.id
    phone = m.contact.phone_number

    cursor.execute("INSERT OR REPLACE INTO users(id, phone, joined) VALUES(?,?,?)",
                   (uid, phone, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

    log(uid, "register")

    bot.send_message(uid, "✅ Ro‘yxatdan o‘tdingiz", reply_markup=types.ReplyKeyboardRemove())
    menu(uid)

# ================= MENU =================
def menu(uid):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Rasm yuborish", callback_data="send"))
    kb.add(types.InlineKeyboardButton("👤 Profil", callback_data="profile"))
    kb.add(types.InlineKeyboardButton("📊 Statistika", callback_data="stat_user"))

    if uid == ADMIN_ID:
        kb.add(types.InlineKeyboardButton("👑 Admin panel", callback_data="admin"))

    bot.send_message(uid, "🏠 Asosiy menyu", reply_markup=kb)

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    uid = c.from_user.id
    user = cursor.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    banned, until = is_banned(user)
    if banned:
        bot.send_message(uid, f"⛔ Ban: {until}")
        return

    if c.data == "send":
        bot.send_message(uid, "📸 Rasm yubor")

    elif c.data == "profile":
        bot.send_message(uid, f"""
👤 Profil
📱 {user[1]}
📸 {user[3]}
✨ {user[4]}
        """)

    elif c.data == "stat_user":
        bot.send_message(uid, f"""
📊 Sizning stat:
📸 {user[3]} yubordingiz
✨ {user[4]} ishlangan
        """)

    elif c.data == "admin" and uid == ADMIN_ID:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📊 Umumiy stat", callback_data="stat"))
        kb.add(types.InlineKeyboardButton("📢 Broadcast", callback_data="bc"))
        kb.add(types.InlineKeyboardButton("🔍 User qidirish", callback_data="find"))
        kb.add(types.InlineKeyboardButton("🔙 Ortga", callback_data="back"))
        bot.send_message(uid, "👑 Admin panel", reply_markup=kb)

    elif c.data == "stat":
        users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bot.send_message(uid, f"👥 Userlar: {users}")

    elif c.data == "bc":
        msg = bot.send_message(uid, "Xabar yubor:")
        bot.register_next_step_handler(msg, broadcast)

    elif c.data == "find":
        msg = bot.send_message(uid, "ID yubor:")
        bot.register_next_step_handler(msg, find_user)

    elif c.data.startswith("hd"):
        process_image(uid, c.data)

    elif c.data == "blur":
        bot.send_message(uid, "🌫 Blur qilindi (demo)")

    elif c.data == "back":
        menu(uid)

# ================= FIND =================
def find_user(m):
    try:
        uid = int(m.text)
        user = cursor.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if user:
            bot.send_message(m.chat.id, f"""
ID: {user[0]}
📱 {user[1]}
📸 {user[3]}
✨ {user[4]}
            """)
    except:
        bot.send_message(m.chat.id, "Xato")

# ================= BROADCAST =================
def broadcast(m):
    users = cursor.execute("SELECT id FROM users").fetchall()
    for u in users:
        try:
            bot.send_message(u[0], m.text)
        except:
            pass
    bot.send_message(m.chat.id, "✅ Yuborildi")

# ================= PHOTO =================
@bot.message_handler(content_types=['photo'])
def photo(m):
    uid = m.from_user.id

    cursor.execute("UPDATE users SET photos=photos+1 WHERE id=?", (uid,))
    conn.commit()

    # ⚠️ NSFW FAKE (keyin AI qo‘shiladi)
    if random.randint(1, 20) == 1:
        ban_user(uid, 60)
        bot.send_message(uid, "🚫 1 soat ban oldingiz")
        return

    file_info = bot.get_file(m.photo[-1].file_id)
    downloaded = bot.download_file(file_info.file_path)

    with open("input.jpg", "wb") as f:
        f.write(downloaded)

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("720p", callback_data="hd_2"))
    kb.add(types.InlineKeyboardButton("1080p", callback_data="hd_4"))
    kb.add(types.InlineKeyboardButton("4K", callback_data="hd_8"))
    kb.add(types.InlineKeyboardButton("🌫 Blur", callback_data="blur"))
    kb.add(types.InlineKeyboardButton("🔙 Ortga", callback_data="back"))

    bot.send_message(uid, "Tanlang:", reply_markup=kb)

# ================= PROCESS =================
def process_image(uid, data):
    scale = int(data.split("_")[1])

    bot.send_message(uid, "⏳ Ishlanyapti...")

    try:
        output = client.run(
            "nightmareai/real-esrgan",
            input={
                "image": open("input.jpg", "rb"),
                "scale": scale
            }
        )

        bot.send_photo(uid, output)

        cursor.execute("UPDATE users SET processed=processed+1 WHERE id=?", (uid,))
        conn.commit()

    except Exception as e:
        bot.send_message(uid, f"❌ Xato: {e}")

# ================= RUN =================
print("🔥 BOT ISHLADI")
bot.infinity_polling()
