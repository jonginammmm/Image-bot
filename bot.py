import telebot
from telebot import types
import sqlite3, threading, queue, time, random, requests
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image, ImageFilter
import replicate

# ===== CONFIG =====
TOKEN = os.getenv "8770225032:AAHGtOVcJOuyMOGihCgm0Ml1AuEeNUm9PO8"
ADMIN_ID = 6394219796
REPLICATE_TOKEN = os.getenv "r8_QQgBmFprXY0vKNqrW0tyr3ja2fSiURe2zMvQJ"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
client = replicate.Client(api_token=REPLICATE_TOKEN)

# ===== DB =====
conn = sqlite3.connect("db.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY,
 photos INT DEFAULT 0,
 processed INT DEFAULT 0,
 bans INT DEFAULT 0,
 premium INT DEFAULT 0,
 daily INT DEFAULT 0,
 last_reset TEXT,
 banned_until TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS logs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 uid INT, action TEXT, time TEXT
)
""")
conn.commit()

# ===== GLOBAL =====
user_images = {}
task_queue = queue.Queue()

# ===== LOG =====
def log(uid, action):
    cur.execute("INSERT INTO logs(uid,action,time) VALUES(?,?,?)",
                (uid, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

# ===== USER =====
def get_user(uid):
    cur.execute("INSERT OR IGNORE INTO users(id,last_reset) VALUES(?,?)",
                (uid, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    return cur.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

def reset_daily(user):
    today = datetime.now().strftime("%Y-%m-%d")
    if user[6] != today:
        cur.execute("UPDATE users SET daily=0,last_reset=? WHERE id=?",
                    (today, user[0]))
        conn.commit()

# ===== BAN =====
def is_banned(user):
    if user[7]:
        until = datetime.strptime(user[7], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < until:
            return True, until
    return False, None

def ban(uid, minutes):
    until = datetime.now() + timedelta(minutes=minutes)
    cur.execute("UPDATE users SET banned_until=?,bans=bans+1 WHERE id=?",
                (until.strftime("%Y-%m-%d %H:%M:%S"), uid))
    conn.commit()

# ===== AI =====
def upscale(img, mode):
    if mode=="720":
        out=client.run("nightmareai/real-esrgan",input={"image":img})
        return out[0]
    if mode=="1080":
        out=client.run("nightmareai/real-esrgan",input={"image":img,"face_enhance":True})
        return out[0]
    if mode=="full":
        a=client.run("nightmareai/real-esrgan",input={"image":img})[0]
        b=client.run("nightmareai/real-esrgan",input={"image":a})
        return b[0]

def watermark(img):
    return client.run("cjwbw/clipdrop-cleanup",input={"image":img})

def nsfw(img):
    try:
        r=client.run("pharmapsychotic/nsfw-detector",input={"image":img})
        return r["nsfw"]
    except:
        return random.randint(1,15)==1

def blur(url, lvl):
    r=requests.get(url)
    im=Image.open(BytesIO(r.content))
    im=im.filter(ImageFilter.GaussianBlur(lvl))
    buf=BytesIO()
    im.save(buf,"JPEG")
    buf.seek(0)
    return buf

# ===== WORKER =====
def worker():
    while True:
        task=task_queue.get()
        uid,mode=task
        try:
            img=user_images[uid]
            bot.send_message(uid,"⏳ Ishlayabman biroz kuting❗...")
            if mode.startswith("hd"):
                m=mode.split("_")[1]
                res=upscale(img,m)
                bot.send_photo(uid,res,caption=f"🔥 {m} HD")
            elif mode=="wm":
                res=watermark(img)
                bot.send_photo(uid,res,caption="💧 Tozalandi")
            elif mode.startswith("blur"):
                lvl=int(mode.split("_")[1])
                res=blur(img,lvl)
                bot.send_photo(uid,res)
            cur.execute("UPDATE users SET processed=processed+1,daily=daily+1 WHERE id=?",(uid,))
            conn.commit()
        except Exception as e:
            bot.send_message(uid,f"❌ Xato: {e}")
        task_queue.task_done()

threading.Thread(target=worker,daemon=True).start()

# ===== MENU =====
def menu(uid):
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Rasim",callback_data="send"))
    kb.add(types.InlineKeyboardButton("👤 Profil",callback_data="profile"))
    if uid==ADMIN_ID:
        kb.add(types.InlineKeyboardButton("👑 Admin",callback_data="admin"))
    bot.send_message(uid,"🏠 Menyu",reply_markup=kb)

# ===== START =====
@bot.message_handler(commands=['start'])
def start(m):
    get_user(m.from_user.id)
    menu(m.from_user.id)

# ===== CALLBACK =====
@bot.callback_query_handler(func=lambda c: True)
def call(c):
    uid=c.from_user.id
    user=get_user(uid)
    reset_daily(user)

    b,u=is_banned(user)
    if b:
        bot.send_message(uid,f"🚫 Ban: {u}")
        return

    if c.data=="send":
        bot.send_message(uid,"📸 Rasm yuboring")

    elif c.data=="profile":
        bot.send_message(uid,f"📸 {user[1]}\n✨ {user[2]}\n💎 {'YES' if user[4] else 'NO'}")

    elif c.data.startswith(("hd","blur","wm")):
        if user[4]==0 and user[5]>=5:
            bot.send_message(uid,"⚠️ Limitiz tugadi (5ta/kun)")
            return
        task_queue.put((uid,c.data))

    elif c.data=="admin" and uid==ADMIN_ID:
        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📊 Statistika",callback_data="stat"))
        kb.add(types.InlineKeyboardButton("🏆 Top",callback_data="top"))
        kb.add(types.InlineKeyboardButton("🔍 Find",callback_data="find"))
        kb.add(types.InlineKeyboardButton("📢 BC",callback_data="bc"))
        bot.send_message(uid,"Admin",reply_markup=kb)

    elif c.data=="stat":
        u=cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bot.send_message(uid,f"👥 {u}")

    elif c.data=="top":
        t=cur.execute("SELECT id,processed FROM users ORDER BY processed DESC LIMIT 5").fetchall()
        txt="\n".join([f"{i[0]} — {i[1]}" for i in t])
        bot.send_message(uid,txt)

    elif c.data=="find":
        msg=bot.send_message(uid,"ID yubor")
        bot.register_next_step_handler(msg,find)

    elif c.data=="bc":
        msg=bot.send_message(uid,"Xabar")
        bot.register_next_step_handler(msg,bc)

def find(m):
    u=cur.execute("SELECT * FROM users WHERE id=?", (m.text,)).fetchone()
    bot.send_message(m.chat.id,str(u))

def bc(m):
    us=cur.execute("SELECT id FROM users").fetchall()
    for i in us:
        try: bot.send_message(i[0],m.text)
        except: pass

# ===== PHOTO =====
@bot.message_handler(content_types=['photo'])
def photo(m):
    uid=m.from_user.id
    user=get_user(uid)

    b,u=is_banned(user)
    if b:
        bot.send_message(uid,"🚫 Ban")
        return

    f=bot.get_file(m.photo[-1].file_id)
    url=f"https://api.telegram.org/file/bot{TOKEN}/{f.file_path}"
    user_images[uid]=url

    cur.execute("UPDATE users SET photos=photos+1 WHERE id=?", (uid,))
    conn.commit()

    if nsfw(url):
        ban(uid,1440)
        bot.send_message(uid,"🚫 1 kun BAN boldiz hurmatli mijoz (18+)")
        return

    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("720",callback_data="hd_720"),
           types.InlineKeyboardButton("1080",callback_data="hd_1080"))
    kb.add(types.InlineKeyboardButton("🔥 FULL",callback_data="hd_full"))
    kb.add(types.InlineKeyboardButton("💧 Watermark",callback_data="wm"))
    kb.add(types.InlineKeyboardButton("🌫 Blur 2",callback_data="blur_2"),
           types.InlineKeyboardButton("🌫 Blur 5",callback_data="blur_5"))
    bot.send_message(uid,"Tanlang:",reply_markup=kb)

# ===== RUN =====
print("🔥 FULL STABLE BOT")
bot.infinity_polling()
