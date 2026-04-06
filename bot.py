import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import random

TOKEN = "8770225032:AAHGtOVcJOuyMOGihCgm0Ml1AuEeNUm9PO8"
ADMIN_ID = 6394219796

bot = telebot.TeleBot(TOKEN)

# ===== DB =====
conn = sqlite3.connect("db.db", check_same_thread=False)
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

# ===== LOG =====
def log(uid, action):
    cursor.execute("INSERT INTO logs(user_id, action, time) VALUES(?,?,?)",
                   (uid, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

# ===== BAN =====
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

# ===== START =====
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

# ===== CONTACT =====
@bot.message_handler(content_types=['contact'])
def contact(m):
    uid = m.from_user.id
    phone = m.contact.phone_number

    cursor.execute("INSERT OR REPLACE INTO users(id, phone, joined) VALUES(?,?,?)",
                   (uid, phone, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

    log(uid, "register")

    bot.send_message(uid, "✅ Tabrikliman Ro‘yxatdan o‘tdingiz", reply_markup=types.ReplyKeyboardRemove())
    menu(uid)

# ===== MENU =====
def menu(uid):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Rasm yuborish", callback_data="send"))
    kb.add(types.InlineKeyboardButton("👤 Profil", callback_data="profile"))

    if uid == ADMIN_ID:
        kb.add(types.InlineKeyboardButton("👑 Admin", callback_data="admin"))

    bot.send_message(uid, "🏠Bosh Menyu", reply_markup=kb)

# ===== CALLBACK =====
@bot.callback_query_handler(func=lambda c: True)
def call(c):
    uid = c.from_user.id
    user = cursor.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    banned, until = is_banned(user)
    if banned:
        bot.send_message(uid, f"⛔ Siz {until} gacha ban yediz")
        return

    if c.data == "send":
        bot.send_message(uid, "📸 Rasm jonating")

    elif c.data == "profile":
        bot.send_message(uid, f"""
👤 Profil

📱 {user[1]}
📸 {user[3]} ta rasm
✨ {user[4]} ta ishlangan
        """)

    elif c.data == "admin" and uid == ADMIN_ID:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📊 Statistika", callback_data="stat"))
        kb.add(types.InlineKeyboardButton("🔍 User qidirish", callback_data="find"))
        kb.add(types.InlineKeyboardButton("📢 Broadcast", callback_data="bc"))
        bot.send_message(uid, "👑 Admin panel", reply_markup=kb)

    elif c.data == "stat":
        users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        photos = cursor.execute("SELECT SUM(photos) FROM users").fetchone()[0]
        bot.send_message(uid, f"👥 {users}\n📸 {photos}")

    elif c.data == "find":
        msg = bot.send_message(uid, "Kimni qidirmoqchisiz IDsini yuboring Topib beraman😁:")
        bot.register_next_step_handler(msg, find_user)

    elif c.data == "bc":
        msg = bot.send_message(uid, "Marahat CoMETA Xabarizni yuboring:")
        bot.register_next_step_handler(msg, broadcast)

    elif c.data.startswith("hd"):
        cursor.execute("UPDATE users SET processed=processed+1 WHERE id=?", (uid,))
        conn.commit()
        bot.send_message(uid, "✨ Rasm HD qilindi (demo)")

    elif c.data.startswith("blur"):
        cursor.execute("UPDATE users SET processed=processed+1 WHERE id=?", (uid,))
        conn.commit()
        bot.send_message(uid, "🌫 Rasm xiralashtirildi (demo)")

    elif c.data == "back":
        menu(uid)

# ===== FIND USER =====
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

# ===== BROADCAST =====
def broadcast(m):
    users = cursor.execute("SELECT id FROM users").fetchall()

    for u in users:
        try:
            bot.send_message(u[0], m.text)
        except:
            pass

    bot.send_message(m.chat.id, "Yuborildi")

# ===== PHOTO =====
@bot.message_handler(content_types=['photo'])
def photo(m):
    uid = m.from_user.id
    user = cursor.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    banned, until = is_banned(user)
    if banned:
        bot.send_message(uid, f"⛔ Ban: {until}")
        return

    cursor.execute("UPDATE users SET photos=photos+1 WHERE id=?", (uid,))
    conn.commit()

    log(uid, "photo_send")

    # ===== FAKE NSFW CHECK =====
    if random.randint(1,10) == 1:
        ban_user(uid, 60)
        bot.send_message(uid, "🚫 Afsus Siz 1 soatga ban oldiz")
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("720p", callback_data="hd_720"))
    kb.add(types.InlineKeyboardButton("1080p", callback_data="hd_1080"))
    kb.add(types.InlineKeyboardButton("Full HD", callback_data="hd_Full HD"))
    kb.add(types.InlineKeyboardButton("Blur 144p", callback_data="blur_144"))
    kb.add(types.InlineKeyboardButton("Blur 240p", callback_data="blur_240"))
    kb.add(types.InlineKeyboardButton("🔙 Ortga", callback_data="back"))

    bot.send_message(uid, "✅Marhatat Tanlang", reply_markup=kb)

# ===== RUN =====
print("🔥 CoMETA BOTIZ ISHLADI❤️❤️❤️")
bot.infinity_polling()
