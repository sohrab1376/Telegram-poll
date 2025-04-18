
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import sqlite3
from aiohttp import web

# تنظیمات لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# خواندن توکن و پورت
TOKEN = os.getenv('TOKEN')
PORT = int(os.getenv('PORT', '10000'))
WEBHOOK_URL = "https://telegram-poll.onrender.com/"

# اتصال به دیتابیس
conn = sqlite3.connect('survey.db', check_same_thread=False)
cursor = conn.cursor()

# ایجاد جدول
cursor.execute('''
CREATE TABLE IF NOT EXISTS responses (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    q1 TEXT,
    q2 TEXT,
    q3 TEXT,
    q4 TEXT,
    q5 TEXT,
    q6 TEXT,
    q7 TEXT,
    q8 TEXT,
    q9 TEXT,
    q10 TEXT,
    medical_id TEXT,
    completed INTEGER DEFAULT 0
)
''')
try:
    cursor.execute('ALTER TABLE responses ADD COLUMN completed INTEGER DEFAULT 0')
except sqlite3.OperationalError:
    pass
conn.commit()

# لیست سوالات
QUESTIONS = [
    "سوال ۱_آیا با روند پرداختی فعلی، دستیابی به اهداف زندگی ممکنه؟",
    "سوال ۲_آیا روند پرداختی درمانگاه‌ها رو نامناسب می‌دونید و حاضر به همکاری برای اصلاحید؟",
    "سوال ۳_در حال حاضر مشغول چه کاری هستید؟",
    "سوال ۴_آیا پروانه طبابت فعال دارید؟",
    "سوال ۵_طی یک ماه گذشته در درمانگاهی کار کردید؟",
    "سوال ۶_آیا با مطالبه کف پرداختی ۴۰۰ ت موافقید؟",
    "سوال ۷_آیا با قطع همکاری با درمانگاه‌ها تا حصول پرداختی مناسب موافقید؟",
    "سوال ۸_آیا با خالی گذاشتن شیفت‌ها در روزهای مشخص موافقید؟",
    "سوال ۹_آیا با قطع همکاری با درمانگاه‌های بدحساب موافقید؟",
    "سوال ۱۰_آیا مشکلات زندگی شما رو مجبور به پر کردن شیفت‌ها کرده؟"
]

# گزینه‌ها
OPTIONS = [
    ["بله", "خیر"],
    ["بله", "خیر"],
    ["طرح اجباری", "خدمت اجباری", "شروع نکردم", "قبلاً سپری کردم"],
    ["بله", "خیر"],
    ["خصوصی <10 شیفت", "خصوصی >10 شیفت", "سایر <10 شیفت", "سایر >10 شیفت", "خیر"],
    ["بله", "خیر"],
    ["بله", "خیر"],
    ["بله", "خیر"],
    ["بله", "خیر"],
    ["بله", "خیر"]
]

# بررسی تکمیل نظرسنجی
async def check_completed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    cursor.execute('SELECT completed FROM responses WHERE user_id = ?', (user.id,))
    result = cursor.fetchone()
    if result and result[0] == 1:
        await update.effective_message.reply_text('شما قبلاً در این نظرسنجی شرکت کرده‌اید.')
        return True
    return False

# شروع نظرسنجی
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await check_completed(update, context):
        return
    user = update.message.from_user
    cursor.execute('SELECT * FROM responses WHERE user_id = ?', (user.id,))
    if not cursor.fetchone():
        cursor.execute('INSERT OR IGNORE INTO responses (user_id, username) VALUES (?, ?)', (user.id, user.username))
        conn.commit()
    context.user_data['question_index'] = 0
    await ask_question(update, context)

# ارسال سوال
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await check_completed(update, context):
        return
    index = context.user_data.get('question_index', 0)
    logger.info(f"Asking question {index} for user {update.effective_user.id}")
    if index < len(QUESTIONS):
        question = QUESTIONS[index]
        options = OPTIONS[index]
        keyboard = [[InlineKeyboardButton(option, callback_data=f"{index}_{option}")] for option in options]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            if update.message:
                await update.message.reply_text(question, reply_markup=reply_markup)
            else:
                await update.callback_query.message.reply_text(question, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error sending question {index}: {e}")
    else:
        await (update.message or update.callback_query.message).reply_text('لطفاً شماره نظام پزشکی خود را وارد کنید:')

# دریافت پاسخ
async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if await check_completed(update, context):
        return
    data = query.data.split('_')
    index = int(data[0])
    answer = data[1]
    user = query.from_user

    logger.info(f"Received response for question {index} from user {user.id}: {answer}")

    cursor.execute('INSERT OR IGNORE INTO responses (user_id, username) VALUES (?, ?)', (user.id, user.username))
    cursor.execute(f'UPDATE responses SET q{index+1} = ? WHERE user_id = ?', (answer, user.id))
    conn.commit()

    context.user_data['question_index'] = index + 1
    logger.info(f"Updated question_index to {context.user_data['question_index']} for user {user.id}")

    await ask_question(update, context)

# دریافت شماره نظام پزشکی
async def handle_medical_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    if await check_completed(update, context):
        return
    if context.user_data.get('question_index', 0) == len(QUESTIONS):
        medical_id = update.message.text
        cursor.execute('UPDATE responses SET medical_id = ?, completed = 1 WHERE user_id = ?', (medical_id, user.id))
        conn.commit()
        await update.message.reply_text('نظرات شما ثبت شد، با تشکر از همکاری شما')
    else:
        await update.message.reply_text('لطفاً ابتدا نظرسنجی را تکمیل کنید.')

# نمایش نتایج
async def results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = 130742264
    user = update.message.from_user
    if user.id != admin_id:
        await update.message.reply_text('شما قبلاً در این نظرسنجی شرکت کرده‌اید.' if await check_completed(update, context) else 'فقط ادمین می‌تونه نتایج رو ببینه!')
        return

    cursor.execute('SELECT * FROM responses')
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("هیچ پاسخی ثبت نشده.")
        return

    response_text = "نتایج نظرسنجی:\n"
    for row in rows:
        response_text += f"کاربر: @{row[1]} (ID: {row[0]})\n"
        for i in range(1, 11):
            response_text += f"سوال {i}: {row[i+1]}\n"
        response_text += f"شماره نظام پزشکی: {row[12]}\n\n"
        if len(response_text) > 3000:
            await update.message.reply_text(response_text)
            response_text = ""

    if response_text:
        await update.message.reply_text(response_text)

# وب‌هوک
async def webhook(request):
    app = request.app['telegram_app']
    try:
        update = Update.de_json(await request.json(), app.bot)
        if update:
            await app.process_update(update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500)

# تابع اصلی
async def main():
    if not TOKEN:
        logger.error("No TOKEN provided")
        return

    app = Application.builder().token(TOKEN).updater(None).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_response))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_medical_id))
    app.add_handler(CommandHandler("results", results))

    web_app = web.Application()
    web_app['telegram_app'] = app
    web_app.router.add_post('/', webhook)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        await app.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return

    await app.initialize()
    await app.start()
    logger.info(f"Bot started on port {PORT}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
