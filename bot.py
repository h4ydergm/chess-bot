import sqlite3
import random
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# ⚠️ ضع التوكن الخاص بك هنا بين علامات التنصيص
TELEGRAM_TOKEN = "8992912265:AAHwgW_SqFBIrPQTA8Z0qy_HUmLFDMmHI6g"

# --- 1. إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect("chess_users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            chesscom_username TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_user(user_id, username):
    conn = sqlite3.connect("chess_users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, chesscom_username) VALUES (?, ?)", (user_id, username.lower()))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("chess_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT chesscom_username FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_all_users():
    conn = sqlite3.connect("chess_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, chesscom_username FROM users")
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- 2. أمر التسجيل (/register) ---
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("يرجى كتابة اسم حسابه في Chess.com بعد الأمر.\nمثال: `/register username`", parse_mode="Markdown")
        return

    username = context.args[0]
    headers = {'User-Agent': 'ChessGroupBot/1.0'}
    res = requests.get(f"https://api.chess.com/pub/player/{username}", headers=headers)
    
    if res.status_code != 200:
        await update.message.reply_text("❌ لم يتم العثور على هذا الحساب في Chess.com. تأكد من الاسم واعد المحاولة.")
        return

    save_user(update.effective_user.id, username)
    await update.message.reply_text(f"✅ تم ربط حسابك التليغرام بحساب Chess.com: `{username}` بنجاح!", parse_mode="Markdown")

# --- 3. أمر التقييمات (/elo) ---
async def elo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    username = get_user(target_user.id)

    if not username:
        await update.message.reply_text(f"❌ الشخص ({target_user.first_name}) غير مسجل في البوت.\nسجل أولاً باﻷمر: `/register username`", parse_mode="Markdown")
        return

    headers = {'User-Agent': 'ChessGroupBot/1.0'}
    res = requests.get(f"https://api.chess.com/pub/player/{username}/stats", headers=headers)

    if res.status_code == 200:
        data = res.json()
        rapid = data.get("chess_rapid", {}).get("last", {}).get("rating", "غير متاح")
        blitz = data.get("chess_blitz", {}).get("last", {}).get("rating", "غير متاح")
        bullet = data.get("chess_bullet", {}).get("last", {}).get("rating", "غير متاح")

        msg = (
            f"🏆 **تقييم اللاعب في Chess.com:** {target_user.first_name} (`{username}`)\n\n"
            f"⏱️ **Rapid:** {rapid}\n"
            f"⚡ **Blitz:** {blitz}\n"
            f"🚀 **Bullet:** {bullet}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text("حدث خطأ أثناء جلب البيانات من Chess.com.")

# --- 4. أمر لوحة الصدارة (/top) ---
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    if not users:
        await update.message.reply_text("لا يوجد أعضاء مسجلين في البوت حالياً.")
        return

    leaderboard = []
    headers = {'User-Agent': 'ChessGroupBot/1.0'}
    
    for uid, uname in users:
        res = requests.get(f"https://api.chess.com/pub/player/{uname}/stats", headers=headers)
        if res.status_code == 200:
            data = res.json()
            blitz = data.get("chess_blitz", {}).get("last", {}).get("rating", 0)
            rapid = data.get("chess_rapid", {}).get("last", {}).get("rating", 0)
            leaderboard.append({'name': uname, 'blitz': blitz, 'rapid': rapid})

    leaderboard.sort(key=lambda x: x['blitz'], reverse=True)

    msg = "🏆 **لوحة صدارة الكروب (Top Blitz):**\n\n"
    for idx, player in enumerate(leaderboard[:10], start=1):
        msg += f"{idx}. `{player['name']}` - ⚡ {player['blitz']} (⏱️ Rapid: {player['rapid']})\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# --- 5. أمر المواجهة المباشرة (/vs) ---
async def vs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("يرجى استخدام الأمر بالرد (Reply) على رسالة الشخص الذي تريد مقارنته معك!")
        return

    user1 = update.effective_user
    user2 = update.message.reply_to_message.from_user

    u1_name = get_user(user1.id)
    u2_name = get_user(user2.id)

    if not u1_name or not u2_name:
        await update.message.reply_text("يجب أن يكون كلا الطرفين مسجلين في البوت عبر الأمر `/register` لاستخدام هذا الأمر.")
        return

    headers = {'User-Agent': 'ChessGroupBot/1.0'}
    r1 = requests.get(f"https://api.chess.com/pub/player/{u1_name}/stats", headers=headers).json()
    r2 = requests.get(f"https://api.chess.com/pub/player/{u2_name}/stats", headers=headers).json()

    msg = (
        f"⚔️ **مواجهة مباشرة (Chess.com)** ⚔️\n\n"
        f"👤 **{user1.first_name}** (`{u1_name}`)\n"
        f"🆚\n"
        f"👤 **{user2.first_name}** (`{u2_name}`)\n\n"
        f"⏱️ **Rapid:** {r1.get('chess_rapid',{}).get('last',{}).get('rating','-')} VS {r2.get('chess_rapid',{}).get('last',{}).get('rating','-')}\n"
        f"⚡ **Blitz:** {r1.get('chess_blitz',{}).get('last',{}).get('rating','-')} VS {r2.get('chess_blitz',{}).get('last',{}).get('rating','-')}\n"
        f"🚀 **Bullet:** {r1.get('chess_bullet',{}).get('last',{}).get('rating','-')} VS {r2.get('chess_bullet',{}).get('last',{}).get('rating','-')}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- 6. أمر التحدي المباشر (/play) ---
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    challenger = update.effective_user.first_name
    
    keyboard = [
        [InlineKeyboardButton("⚔️ قبول التحدي وإنشاء رقعة (3+2)", url="https://lichess.org/clock?time=3&increment=2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        f"⚔️ **تحدي بلتز جديد!**\n\n"
        f"👤 **المُتحدّي:** {challenger}\n"
        f"⏱️ **الوقت:** 3 دقائق + 2 ثانية زيادة (Blitz)\n\n"
        f"اضغط على الزر أدناه للبدء باللعب مباشرة على Lichess!"
    )
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

# --- 7. أمر الافتتاحيات (/opening) ---
async def opening(update: Update, context: ContextTypes.DEFAULT_TYPE):
    openings = [
        {"name": "الدفاع الصقلي (Sicilian Defense)", "code": "B20", "moves": "1. e4 c5"},
        {"name": "افتتاحية الرُوي لوبيز (Ruy Lopez)", "code": "C60", "moves": "1. e4 e5 2. Nf3 Nc6 3. Bb5"},
        {"name": "جامبت الوزير (Queen's Gambit)", "code": "D06", "moves": "1. d4 d5 2. c4"},
        {"name": "الدفاع الفرنسي (French Defense)", "code": "C00", "moves": "1. e4 e6"},
        {"name": "دفاع الكارو-كان (Caro-Kann Defense)", "code": "B10", "moves": "1. e4 c6"},
        {"name": "الدفاع الهندي للملك (King's Indian Defense)", "code": "E60", "moves": "1. d4 Nf6 2. c4 g6"}
    ]
    item = random.choice(openings)
    msg = (
        f"📖 **افتتاحية اليوم:**\n\n"
        f"📌 **الاسم:** {item['name']}\n"
        f"🏷️ **الرمز (ECO):** {item['code']}\n"
        f"♟️ **النقلات المفتاحية:** `{item['moves']}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- 8. أمر المقولات (/quote) ---
async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "«الشطرنج هي الحياة مصغرة.» — غاري كاسباروف",
        "«كل ما يهمني هو اللعب والتغلب على المنافس.» — بوبي فيشر",
        "«تضحية البيدق في الوقت المناسب قد تهدم أعتى الخطط.» — ميخائيل تال",
        "«لا أؤمن بالسحر، أؤمن بالنقلة القوية فقط.» — ماغنوس كارلسن",
        "«الشطرنج حرب فوق الرقعة، والهدف هو تحطيم عقل الخصم.» — بوبي فيشر"
    ]
    await update.message.reply_text(f"💬 {random.choice(quotes)}")

# --- 9. أمر اللغز اليومي (/puzzle) ---
async def puzzle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = requests.get("https://lichess.org/api/puzzle/daily")
    if res.status_code == 200:
        data = res.json()
        puzzle_id = data["puzzle"]["id"]
        puzzle_rating = data["puzzle"]["rating"]
        game_url = f"https://lichess.org/training/{puzzle_id}"
        
        msg = (
            f"🧩 **لغز اليوم من Lichess:**\n\n"
            f"⭐ **التقييم:** {puzzle_rating}\n"
            f"🔗 **رابط اللغز:** {game_url}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

# --- التشغيل الرئيسي ---
def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("elo", elo))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("leaderboard", top))
    app.add_handler(CommandHandler("vs", vs))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("opening", opening))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("puzzle", puzzle))

    print("🤖 البوت يعمل الآن بنجاح...")
    app.run_polling()

if __name__ == "__main__":
    main()