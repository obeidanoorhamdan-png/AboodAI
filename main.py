import logging
import os
import json
import base64
import asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env (للحماية)
load_dotenv()

# --- الإعدادات ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6207431030"))
CHANNEL_LINK = "https://t.me/Sz2zv"
ADMIN_USERNAME = "@Sz2zv"
POINTS_PER_REF = 5
DB_FILE = "database.json"

client = OpenAI(api_key=OPENAI_API_KEY)

# إعداد السجلات (Logs)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- إدارة قاعدة البيانات ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db, f, indent=4, ensure_ascii=False)

users_db = load_db()

# --- معالج الأخطاء ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"⚠️ Error: {context.error}")

# --- أوامر الأدمن ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    total_users = len(users_db)
    await update.message.reply_text(f"📊 إحصائيات البوت:\n- إجمالي المستخدمين: {total_users}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg_text = " ".join(context.args)
    if not msg_text:
        await update.message.reply_text("❌ يرجى كتابة الرسالة بعد الأمر.")
        return
    
    status = await update.message.reply_text("⏳ جاري الإرسال...")
    success, fail = 0, 0
    for user_id in list(users_db.keys()):
        try:
            await context.bot.send_message(chat_id=int(user_id), text=msg_text)
            success += 1
            await asyncio.sleep(0.05)
        except: fail += 1
    await status.edit_text(f"✅ تم الإرسال!\n- نجاح: {success}\n- فشل: {fail}")

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        t_id, amt = context.args[0], int(context.args[1])
        if t_id in users_db:
            users_db[t_id]['points'] += amt
            save_db(users_db)
            await update.message.reply_text(f"✅ تمت إضافة {amt} نقطة للحساب {t_id}")
            try: await context.bot.send_message(chat_id=int(t_id), text=f"🎁 تمت إضافة {amt} نقطة لرصيدك!")
            except: pass
    except: await update.message.reply_text("استخدم: /add [ID] [Points]")

# --- معالجة المحتوى ---
async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in users_db: users_db[user_id] = {'points': 10, 'history': [], 'referrals': 0}
    
    text = update.message.text

    if text == '👤 حسابي':
        u = users_db[user_id]
        await update.message.reply_text(f"👤 **بيانات حسابك:**\n💰 النقاط: {u.get('points',0)}\n👥 الإحالات: {u.get('referrals',0)}\n🆔 الآيدي: `{user_id}`", parse_mode='Markdown')
        return
    elif text == '🔗 رابط الإحالة':
        bot_info = await context.bot.get_me()
        await update.message.reply_text(f"🎁 **اربح نقاط!**\n\nستحصل على {POINTS_PER_REF} نقاط لكل شخص ينضم عبر رابطك:\n`https://t.me/{bot_info.username}?start={user_id}`", parse_mode='Markdown')
        return
    elif text == '📢 قناة البوت':
        await update.message.reply_text("قناتنا الرسمية:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 انضم هنا", url=CHANNEL_LINK)]]))
        return
    elif text == '💰 شراء نقاط':
        await update.message.reply_text(f"تواصل مع الإدارة لشحن الرصيد: {ADMIN_USERNAME}")
        return

    if update.message.photo:
        if users_db[user_id].get('points', 0) < 1:
            await update.message.reply_text("⚠️ رصيدك 0. ادعُ أصدقاءك للحصول على نقاط.")
            return
        status = await update.message.reply_text("⏳ جاري تحليل الشارت...")
        try:
            photo = await update.message.photo[-1].get_file()
            path = f"img_{user_id}.jpg"
            await photo.download_to_drive(path)
            with open(path, "rb") as f: b64 = base64.b64encode(f.read()).decode('utf-8')
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": [{"type":"text","text":"حلل هذا الشارت بدقة كخبير تداول."}, {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}]
            )
            users_db[user_id]['points'] -= 1
            save_db(users_db)
            await status.delete()
            await update.message.reply_text(f"✅ **التحليل الفني:**\n\n{res.choices[0].message.content}", parse_mode='Markdown')
            os.remove(path)
        except Exception as e:
            logging.error(e)
            await status.edit_text("❌ فشل التحليل.")

    elif text and not text.startswith('/'):
        thinking = await update.message.reply_text("🤖 جاري التفكير...")
        try:
            msgs = [{"role": "system", "content": "أنت مساعد خبير تداول."}]
            for h in users_db[user_id].get('history', [])[-3:]:
                msgs.append({"role":"user","content":h['u']}), msgs.append({"role":"assistant","content":h['b']})
            msgs.append({"role":"user","content":text})
            res = client.chat.completions.create(model="gpt-4o-mini", messages=msgs)
            ans = res.choices[0].message.content
            users_db[user_id].setdefault('history', []).append({'u': text, 'b': ans})
            save_db(users_db)
            await thinking.delete()
            await update.message.reply_text(ans)
        except: await thinking.edit_text("❌ حدث خطأ.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in users_db:
        users_db[user_id] = {'points': 10, 'history': [], 'referrals': 0}
        if context.args:
            ref_id = context.args[0]
            if ref_id in users_db and ref_id != user_id:
                users_db[ref_id]['points'] += POINTS_PER_REF
                users_db[ref_id]['referrals'] += 1
                try: await context.bot.send_message(chat_id=int(ref_id), text="🎁 حصلت على نقاط من إحالة جديدة!")
                except: pass
        save_db(users_db)
    
    keyboard = [['📊 تحليل صورة', '👤 حسابي'], ['🔗 رابط الإحالة', '📢 قناة البوت'], ['💰 شراء نقاط']]
    await update.message.reply_text("🚀 مرحباً بك! أنا مساعدك الذكي في التداول.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

def main():
    if not BOT_TOKEN:
        print("❌ خطأ: لم يتم العثور على توكن البوت في متغيرات البيئة!")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("add", add_points))
    app.add_handler(MessageHandler(filters.ALL, handle_all))
    app.add_error_handler(error_handler)
    print("🚀 البوت يعمل الآن...")
    app.run_polling()

if __name__ == '__main__': main()
