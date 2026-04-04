import telebot
from flask import Flask
import threading
from telebot import types
app = Flask('')

@app.route('/')
def home():
    return "Alive"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()
import sqlite3
import os
import cv2
from datetime import datetime
import time

TOKEN = "8770225032:AAHkrpbuD0Ga88YWmjK9dzOSEzrDm2EBY_Y"
ADMIN_ID = 6394219796

bot = telebot.TeleBot(TOKEN)

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

LIMIT = 6
user_data = {}

# ===== MENU =====
def menu(uid):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Rasm yuborish", callback_data="send"))
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

    bot.send_message(uid,"🤖 AI IMAGE BOTga xushkebsz\n📸 Marhamat Rasm yuboring",
                     reply_markup=menu(uid))

# ===== LIMIT =====
def check_limit(uid):
    if uid == ADMIN_ID:
        return True

    today = datetime.now().strftime("%Y-%m-%d")
    data = cursor.execute("SELECT count,last_date FROM users WHERE id=?",(uid,)).fetchone()

    if data[1] != today:
        cursor.execute("UPDATE users SET count=0,last_date=? WHERE id=?",(today,uid))
        conn.commit()
        return True

    if data[0] >= LIMIT:
        return False

    return True

def add_count(uid):
    cursor.execute("UPDATE users SET count=count+1 WHERE id=?",(uid,))
    conn.commit()

# ===== CALLBACK =====
@bot.callback_query_handler(func=lambda c: True)
def call(c):
    uid = c.from_user.id

    # BAN CHECK
    banned = cursor.execute("SELECT banned FROM users WHERE id=?",(uid,)).fetchone()[0]
    if banned:
        bot.answer_callback_query(c.id,"🚫 Siz bloklangansiz")
        return

    if c.data == "back":
        bot.edit_message_text("🏠 Menu",c.message.chat.id,c.message.message_id,
                              reply_markup=menu(uid))

    elif c.data == "send":
        bot.edit_message_text("📸 Rasm yuboring",c.message.chat.id,c.message.message_id,
                              reply_markup=back())

    elif c.data == "settings":
        wm = cursor.execute("SELECT watermark FROM users WHERE id=?",(uid,)).fetchone()[0]
        status = "ON" if wm else "OFF"

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(f"💧 Watermark: {status}",callback_data="wm"))
        kb.add(types.InlineKeyboardButton("🔙 Orqaga",callback_data="back"))

        bot.edit_message_text("⚙️ Sozlamalar",c.message.chat.id,c.message.message_id,
                              reply_markup=kb)

    elif c.data == "wm":
        wm = cursor.execute("SELECT watermark FROM users WHERE id=?",(uid,)).fetchone()[0]
        cursor.execute("UPDATE users SET watermark=? WHERE id=?",(0 if wm else 1,uid))
        conn.commit()
        bot.answer_callback_query(c.id,"✅ O‘zgardi")

    # ===== ADMIN PANEL =====
    elif c.data == "admin" and uid == ADMIN_ID:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📊 Stat",callback_data="stat"))
        kb.add(types.InlineKeyboardButton("📢 Broadcast",callback_data="broadcast"))
        kb.add(types.InlineKeyboardButton("🚫 Ban",callback_data="ban"))
        kb.add(types.InlineKeyboardButton("✅ Unban",callback_data="unban"))
        kb.add(types.InlineKeyboardButton("🔙 Orqaga",callback_data="back"))

        bot.edit_message_text("👑CoMETA Admin paneli",c.message.chat.id,c.message.message_id,
                              reply_markup=kb)

    elif c.data == "stat" and uid == ADMIN_ID:
        users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bot.send_message(uid,f"👥 Users: {users}")

    elif c.data == "broadcast" and uid == ADMIN_ID:
        msg = bot.send_message(uid,"✍️ Xabar yuboring")
        bot.register_next_step_handler(msg, send_broadcast)

    elif c.data == "ban" and uid == ADMIN_ID:
        msg = bot.send_message(uid,"🚫 ID yubor")
        bot.register_next_step_handler(msg, do_ban)

    elif c.data == "unban" and uid == ADMIN_ID:
        msg = bot.send_message(uid,"✅ ID yubor")
        bot.register_next_step_handler(msg, do_unban)

# ===== ADMIN FUNCTIONS =====
def send_broadcast(m):
    users = cursor.execute("SELECT id FROM users").fetchall()
    for u in users:
        try:
            bot.send_message(u[0],m.text)
        except:
            pass

def do_ban(m):
    cursor.execute("UPDATE users SET banned=1 WHERE id=?",(int(m.text),))
    conn.commit()
    bot.send_message(m.chat.id,"🚫 Ban qilindi")

def do_unban(m):
    cursor.execute("UPDATE users SET banned=0 WHERE id=?",(int(m.text),))
    conn.commit()
    bot.send_message(m.chat.id,"✅ Unban qilindi")

# ===== PHOTO =====
@bot.message_handler(content_types=['photo'])
def photo(m):
    uid = m.from_user.id

    if not check_limit(uid):
        bot.send_message(uid,"🚫Bugingi Limit tugadi")
        return

    msg = bot.send_message(uid,"⏳ 10%")

    file = bot.get_file(m.photo[-1].file_id)
    data = bot.download_file(file.file_path)

    path = f"{uid}.jpg"
    open(path,"wb").write(data)

    bot.edit_message_text("⏳ 30%",uid,msg.message_id)
    time.sleep(1)

    img = cv2.imread(path)
    h,w = img.shape[:2]

    scale = 4 if w < 500 else 2
    img = cv2.resize(img,(w*scale,h*scale),interpolation=cv2.INTER_CUBIC)

    bot.edit_message_text("⏳ 60%",uid,msg.message_id)
    time.sleep(1)

    out = f"hd_{uid}.jpg"
    cv2.imwrite(out,img)

    bot.edit_message_text("⏳ 90%",uid,msg.message_id)
    time.sleep(1)

    bot.send_photo(uid,open(path,"rb"),caption="📷 Original")
    bot.send_photo(uid,open(out,"rb"),caption="✨ HD")

    bot.edit_message_text("✅ Tayyor 100%",uid,msg.message_id)

    add_count(uid)

    os.remove(path)
    os.remove(out)

# ===== RUN =====
print("CoMETA SIZ yaratgan Bot ishga tushdi 🔥")
keep_alive()
bot.infinity_polling()
