
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

# خواندن توکن و پورت از متغیرهای محیطی
TOKEN = os.getenv('TOKEN')
PORT = int(os.getenv('PORT', '10000'))  # پورت پیش‌فرض 10000 برای Render
WEBHOOK_URL = "https://telegram-poll.onrender.com/"

# اتصال به دیتابیس SQLite
conn = sqlite3.connect('survey.db', check_same_thread=False)
cursor = conn.cursor()

# ایجاد جدول برای ذخیره پاسخ‌ها
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
    medical_id TEXT
)
''')
conn.commit()

# لیست سوالات
QUESTIONS = [
    "سوال ۱_همکار گرامی آیا با روند پرداختی های فعلی، دستیابی به اهداف کوتاه مدت و بلند مدت زندگی خود را، در شان یک پزشک، ممکن می‌دانید؟",
    "سوال ۲_همکار گرامی آیا روند کنونی پرداختی های درمانگاه ها را نامناسب میدانید و برای اصلاح آن حاضر به همکاری هستید؟!",
    "سوال ۳_همکار گرامی در حال حاضر مشغول سپری کردن کدام یک از موارد زیر هستید؟!",
    "سوال ۴_همکار گرامی آیا در حال حاضر پروانه طبابت فعال، پروانه موقت و یا نامه عدم نیاز در ساعات غیر اداری در اختیار دارید؟!",
    "سوال ۵_همکار گرامی آیا طی یک ماهه گذشته در درمانگاهی مشغول به کار بوده اید؟",
    "سوال ۶_همکار گرامی آیا با مطالبه «کف پرداختی ساعتی ۴۰۰ ت همراه با ۲۵ درصد خدمات و ۵۰ درصد پروسیژر» و یا «پرکیس معادل کا حرفه ای درصورت ویزیت میانگین بیشتر از ۴ بیمار در ساعت» و عدم پذیرش همکاری با نرخ کمتر از این مقدار به صورت علل حساب تا زمان حصول یک فرمول جامع موافق هستید؟!",
    "سوال ۷_همکار گرامی آیا در صورت تصمیم جمعی مبنی بر \"قطع کامل هرگونه همکاری با درمانگاهداران و عدم تمدید قرارداد تا حصول پرداختی قابل قبول\" با این حرکت اعتراضی همراه خواهید بود؟!",
    "سوال ۸_همکار گرامی آیا در صورت تصمیم جمعی مبنی بر \"برنداشتن شیفت، خالی گذاشتن و کاور نکردن آن ها فقط در روز های مشخصی از هر ماه\" با این حرکت اعتراضی همراه خواهید بود؟!",
    "سوال ۹_همکار گرامی آیا در صورت تصمیم جمعی مبنی بر \"قطع هرگونه همکاری و عدم تمدید قرارداد با تعداد مشخصی از درمانگاه های بدحساب\" با این حرکت اعتراضی همراه خواهید بود؟!",
    "سوال ۱۰_همکار گرامی آیا مسائل و مشکلات زندگی و یا سایر دلایل شما را مجبور به پر کردن شیفت ها تحت هر شرایطی کرده؟!"
]

# گزینه‌های هر سوال
OPTIONS = [
    ["بله", "خیر"],
    ["بله", "خیر"],
    ["طرح اجباری", "خدمت اجباری", "هنوز طرح یا خدمت اجباری را شروع نکردم", "طرح یا خدمت اجباری را قبلا سپری کردم"],
    ["بله", "خیر"],
    ["درمانگاه خصوصی کمتر از 10 شیفت", "درمانگاه خصوصی بیشتر از 10 شیفت", "سایر مراکز کمتر از 10 شیفت", "سایر مراکز بیشتر از 10 شیفت", "خیر"],
    ["بله", "خیر"],
    ["بله", "خیر"],
    ["بله", "خیر"],
    ["بله", "خیر"],
    ["بله", "خیر"]
]

# تابع شروع نظرسنجی
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    cursor.execute('SELECT * FROM responses WHERE user_id = ?', (user.id,))
    if cursor.fetchone():
        await update.message.reply_text('شما قبلاً در این نظرسنجی شرکت کرده‌اید.')
        return
    context.user_data['question_index'] = 0
    await ask_question(update, context)

# تابع ارسال سوال
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    index = context.user_data['question_index']
    if index < len(QUESTIONS):
        question = QUESTIONS[index]
        options = OPTIONS[index]
        keyboard = [[InlineKeyboardButton(option, callback_data=f"{index}_{option}")] for option in options]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text(question, reply_markup=reply_markup)
        else:
            await update.callback_query.message.reply_text(question, reply_markup=reply_markup)
    else:
        await (update.message or update.callback_query.message).reply_text('لطفاً شماره نظام پزشکی خود را وارد کنید:')

# تابع دریافت پاسخ سوالات
async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    index = int(data[0])
    answer = data[1]
    user = query.from_user

    cursor.execute('INSERT OR IGNORE INTO responses (user_id, username) VALUES (?, ?)', (user.id, user.username))
    cursor.execute(f'UPDATE responses SET q{index+1} = ? WHERE user_id = ?', (answer, user.id))
    conn.commit()

    context.user_data['question_index'] += 1
    await ask_question(update, context)

# تابع دریافت شماره نظام پزشکی
async def handle_medical_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    medical_id = update.message.text
    cursor.execute('UPDATE responses SET medical_id = ? WHERE user_id = ?', (medical_id, user.id))
    conn.commit()
    await update.message.reply_text('نظرات شما ثبت شد، با تشکر از همکاری شما')

# تابع برای نمایش نتایج (فقط برای ادمین)
async def results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = 130742264  # آیدی تلگرام تو
    if update.message.from_user.id != admin_id:
        await update.message.reply_text("فقط ادمین می‌تونه نتایج رو ببینه!")
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
        if len(response_text) > 3000:  # جلوگیری از محدودیت طول پیام
            await update.message.reply_text(response_text)
            response_text = ""

    if response_text:
        await update.message.reply_text(response_text)

# تابع مدیریت درخواست‌های وب‌هوک
async def webhook(request):
    app = request.app['telegram_app']
    update = Update.de_json(await request.json(), app.bot)
    await app.process_update(update)
    return web.Response()

# تابع اصلی
async def main():
    # بررسی توکن
    if not TOKEN:
        logger.error("No TOKEN provided in environment variables")
        return

    # تنظیم ربات تلگرام
    app = Application.builder().token(TOKEN).build()

    # ثبت هندلرها
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_response))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_medical_id))
    app.add_handler(CommandHandler("results", results))

    # تنظیم سرور aiohttp
    web_app = web.Application()
    web_app['telegram_app'] = app
    web_app.router.add_post('/', webhook)

    # راه‌اندازی سرور
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    # تنظیم صریح وب‌هوک
    await app.bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

    # شروع اپلیکیشن
    await app.initialize()
    await app.start()
    logger.info(f"Bot started on port {PORT}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
