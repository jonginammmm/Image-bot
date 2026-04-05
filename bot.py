import telebot
from flask import Flask
import threading
from telebot import types
import sqlite3
import os
import requests
import time
from datetime import datetime

# ===== CONFIG =====
TOKEN = os.getenv"8770225032:AAHeeR2vzqoqq3ZGJGiPScAotfNropL5314
ADMIN_ID =  6394219796 # o'z telegram id'ingni yoz

bot = telebot.TeleBot(TOKEN)

# ===== KEEP ALIVE =====
app = Flask(__name__)

@app.route('/'")
def home():
    return "Alive"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

# ===== DB =====
conn = sqlite3.connect("db.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    count INT DEFAULT 0,
    last_date TEXT,
    watermark INT DEFAULT 1,
    banned INT DEFAULT 0
)
""")
conn.commit()

LIMIT = 5

# ===== MENU =====
def menu(uid):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Rasm jonatish", callback_data="send"))
    kb.add(types.InlineKeyboardButton("⚙️ Sozlamalar", callback_data="settings"))
    if uid == ADMIN_ID:
        kb.add(types.InlineKeyboardButton("👑 Admin panel", callback_data="admin"))
    return kb

def back():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back"))
    return kb

# ===== START =====
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id

    cursor.execute("INSERT OR IGNORE INTO users(id,last_date) VALUES(?,?)",
                   (uid, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()

    bot.send_message(uid,
        "🤖 AI IMAGE BOTga xushkebsz\n\n📸 Marhamat Rasm jonating",
        reply_markup=menu(uid)
    )

# ===== LIMIT =====
def check_limit(uid):
    if uid == ADMIN_ID:
        return True

    today = datetime.now().strftime("%Y-%m-%d")
    data = cursor.execute("SELECT count,last_date FROM users WHERE id=?", (uid,)).fetchone()

    if data[1] != today:
        cursor.execute("UPDATE users SET count=0,last_date=? WHERE id=?", (today, uid))
        conn.commit()
        return True

    if data[0] >= LIMIT:
        return False

    return True

def add_count(uid):
    cursor.execute("UPDATE users SET count=count+1 WHERE id=?", (uid,))
    conn.commit()

# ===== CALLBACK =====
@bot.callback_query_handler(func=lambda c: True)
def call(c):
    uid = c.from_user.id

    banned = cursor.execute("SELECT banned FROM users WHERE id=?", (uid,)).fetchone()[0]
    if banned:
        bot.answer_callback_query(c.id, "🚫 Siz bloklangansiz")
        return

    if c.data == "back":
        bot.edit_message_text("🏠 Menu", c.message.chat.id, c.message.message_id,
                              reply_markup=menu(uid))

    elif c.data == "send":
        bot.edit_message_text("📸 Rasm jonating", c.message.chat.id, c.message.message_id,
                              reply_markup=back())

    elif c.data == "settings":
        wm = cursor.execute("SELECT watermark FROM users WHERE id=?", (uid,)).fetchone()[0]
        status = "ON" if wm else "OFF"

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(f"💧 Watermark: {status}", callback_data="wm"))
        kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back"))

        bot.edit_message_text("⚙️ Sozlamalar", c.message.chat.id, c.message.message_id,
                              reply_markup=kb)

    elif c.data == "wm":
        wm = cursor.execute("SELECT watermark FROM users WHERE id=?", (uid,)).fetchone()[0]
        cursor.execute("UPDATE users SET watermark=? WHERE id=?", (0 if wm else 1, uid))
        conn.commit()
        bot.answer_callback_query(c.id, "✅ O‘zgardi")

    # ===== ADMIN =====
    elif c.data == "admin" and uid == ADMIN_ID:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📊 Statistika", callback_data="stat"))
        kb.add(types.InlineKeyboardButton("📢 Broadcast", callback_data="broadcast"))
        kb.add(types.InlineKeyboardButton("🚫 Ban", callback_data="ban"))
        kb.add(types.InlineKeyboardButton("✅ Unban", callback_data="unban"))
        kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back"))

        bot.edit_message_text("👑 Admin panel", c.message.chat.id, c.message.message_id,
                              reply_markup=kb)

    elif c.data == "stat" and uid == ADMIN_ID:
        users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bot.send_message(uid, f"👥 Users: {users}")

    elif c.data == "broadcast" and uid == ADMIN_ID:
        msg = bot.send_message(uid, "✍️ CoMETA botizga Xabar yuboring")
        bot.register_next_step_handler(msg, send_broadcast)

    elif c.data == "ban" and uid == ADMIN_ID:
        msg = bot.send_message(uid, "🚫 ID yubor")
        bot.register_next_step_handler(msg, do_ban)

    elif c.data == "unban" and uid == ADMIN_ID:
        msg = bot.send_message(uid, "✅ ID yubor")
        bot.register_next_step_handler(msg, do_unban)

# ===== ADMIN FUNCTIONS =====
def send_broadcast(m):
    users = cursor.execute("SELECT id FROM users").fetchall()
    for u in users:
        try:
            bot.send_message(u[0], m.text)
        except:
            pass

def do_ban(m):
    cursor.execute("UPDATE users SET banned=1 WHERE id=?", (int(m.text),))
    conn.commit()
    bot.send_message(m.chat.id, "🚫 Ban qilindiz")

def do_unban(m):
    cursor.execute("UPDATE users SET banned=0 WHERE id=?", (int(m.text),))
    conn.commit()
    bot.send_message(m.chat.id, "✅ Unban qilindingiz")

# ===== PHOTO =====
@bot.message_handler(content_types=['photo'])
def photo(m):
    uid = m.from_user.id

    if not check_limit(uid):
        bot.send_message(uid, "🚫 Limitiz tugadi")
        return

    msg = bot.send_message(uid, "⏳ Ishlayapti...")

    file = bot.get_file(m.photo[-1].file_id)
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"

    # vaqtinchalik AI o‘rniga qaytaradi (test uchun)
    bot.send_photo(uid, file_url, caption="✅ Tayyor")
    bot.delete_message(uid, msg.message_id)

    add_count(uid)

# ===== RUN =====
print("🔥 CoMETA 4KRasm BOTiz ISHLADI marhamat foydalanishiz mumkin")
keep_alive()
bot.infinity_polling()
