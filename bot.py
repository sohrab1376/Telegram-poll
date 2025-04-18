
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

# لیست سوالات (تمیز شده)
QUESTIONS = [
    "سوال 1_همکار گرامی آیا با روند پرداختی های فعلی دستیابی به اهداف کوتاه مدت و بلند مدت زندگی خود را در شان یک پزشک ممکن میدانید",
    "سوال 2_همکار گرامی آیا روند کنونی پرداختی های درمانگاه ها را نامناسب میدانید و برای اصلاح آن حاضر به همکاری هستید",
    "سوال 3_همکار گرامی در حال حاضر مشغول سپری کردن کدام یک از موارد زیر هستید",
    "سوال 4_همکار گرامی آیا در حال حاضر پروانه طبابت فعال پروانه موقت و یا نامه عدم نیاز در ساعات غیر اداری در اختیار دارید",
    "سوال 5_همکار گرامی آیا طی یک ماهه گذشته در درمانگاهی مشغول به کار بوده اید",
    "سوال 6_همکار گرامی آیا با مطالبه کف پرداختی ساعتی 400 ت همراه با 25 درصد خدمات و 50 درصد پروسیژر و یا پرکیس معادل کا حرفه ای درصورت ویزیت میانگین بیشتر از 4 بیمار در ساعت و عدم پذیرش همکاری با نرخ کمتر از این مقدار به صورت علل حساب تا زمان حصول یک فرمول جامع موافق هستید",
    "سوال 7_همکار گرامی آیا در صورت تصمیم جمعی مبنی بر قطع کامل هرگونه همکاری با درمانگاهداران و عدم تمدید قرارداد تا حصول پرداختی قابل قبول با این حرکت اعتراضی همراه خواهید بود",
    "سوال 8_همکار گرامی آیا در صورت تصمیم جمعی مبنی بر برنداشتن شیفت خالی گذاشتن و کاور نکردن آن ها فقط در روز های مشخصی از هر ماه با این حرکت اعتراضی همراه خواهید بود",
    "سوال 9_همکار گرامی آیا در صورت تصمیم جمعی مبنی بر قطع هرگونه همکاری و عدم تمدید قرارداد با تعداد مشخصی از درمانگاه های بدحساب با این حرکت اعتراضی همراه خواهید بود",
    "سوال 10_همکار گرامی آیا مسائل و مشکلات زندگی و یا سایر دلایل شما را مجبور به پر کردن شیفت ها تحت هر شرایطی کرده"
]

# گزینه‌های هر سوال (نمایش فارسی، callback_data لاتین)
OPTIONS = [
    [("بله", "yes"), ("خیر", "no")],
    [("بله", "yes"), ("خیر", "no")],
    [("طرح اجباری", "mandatory_plan"), ("خدمت اجباری", "mandatory_service"), ("هنوز طرح یا خدمت اجباری را شروع نکردم", "not_started"), ("طرح یا خدمت اجباری را قبلا سپری کردم", "completed")],
    [("بله", "yes"), ("خیر", "no")],
    [("درمانگاه خصوصی کمتر از 10 شیفت", "private_less_10"), ("درمانگاه خصوصی بیشتر از 10 شیفت", "private_more_10"), ("سایر مراکز کمتر از 10 شیفت", "other_less_10"), ("سایر مراکز بیشتر از 10 شیفت", "other_more_10"), ("خیر", "no")],
    [("بله", "yes"), ("خیر", "no")],
    [("بله", "yes"), ("خیر", "no")],
    [("بله", "yes"), ("خیر", "no")],
    [("بله", "yes"), ("خیر", "no")],
    [("بله", "yes"), ("خیر", "no")]
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
    logger.info(f"Started survey for user {user.id}")
    await ask_question(update, context)

# ارسال سوال
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await check_completed(update, context):
        return
    index = context.user_data.get('question_index', 0)
    user = update.effective_user
    logger.info(f"Asking question {index} for user {user.id}")
    if index < len(QUESTIONS):
        question = QUESTIONS[index]
        options = OPTIONS[index]
        keyboard = [[InlineKeyboardButton(text, callback_data=f"{index}_{data}")] for text, data in options]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            if update.message:
                await update.message.reply_text(question, reply_markup=reply_markup)
            else:
                await update.callback_query.message.reply_text(question, reply_markup=reply_markup)
            logger.info(f"Sent question {index} to user {user.id} with callback_data: {[f'{index}_{data}' for _, data in options]}")
        except Exception as e:
            logger.error(f"Error sending question {index} to user {user.id}: {e}")
            await (update.message or update.callback_query.message).reply_text("خطایی در ارسال سوال رخ داد. لطفاً دوباره سعی کنید.")
    else:
        logger.info(f"Reached end of questions for user {user.id}, asking for medical ID")
        await (update.message or update.callback_query.message).reply_text('لطفاً شماره نظام پزشکی خود را وارد کنید:')

# دریافت پاسخ
async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if await check_completed(update, context):
        return
    user = query.from_user
    logger.info(f"Processing response for user {user.id}")
    try:
        data = query.data.split('_')
        index = int(data[0])
        answer = data[1]
        logger.info(f"Received response for question {index} from user {user.id}: {answer}")

        # تبدیل callback_data به متن نمایش
        for text, cb_data in OPTIONS[index]:
            if cb_data == answer:
                answer_text = text
                break
        else:
            logger.error(f"Invalid callback_data for question {index} from user {user.id}: {answer}")
            await query.message.reply_text("گزینه نامعتبر. لطفاً دوباره سعی کنید.")
            return

        cursor.execute('INSERT OR IGNORE INTO responses (user_id, username) VALUES (?, ?)', (user.id, user.username))
        cursor.execute(f'UPDATE responses SET q{index+1} = ? WHERE user_id = ?', (answer_text, user.id))
        conn.commit()
        logger.info(f"Saved response for question {index} for user {user.id}: {answer_text}")

        context.user_data['question_index'] = index + 1
        logger.info(f"Updated question_index to {context.user_data['question_index']} for user {user.id}")

        await ask_question(update, context)
        logger.info(f"Triggered ask_question for index {context.user_data['question_index']} for user {user.id}")
    except Exception as e:
        logger.error(f"Error in handle_response for user {user.id}: {e}")
        await query.message.reply_text("خطایی رخ داد. لطفاً دوباره سعی کنید.")

# دریافت شماره نظام پزشکی
async def handle_medical_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    if await check_completed(update, context):
        return
    if context.user_data.get('question_index', 0) == len(QUESTIONS):
        medical_id = update.message.text
        cursor.execute('UPDATE responses SET medical_id = ?, completed = 1 WHERE user_id = ?', (medical_id, user.id))
        conn.commit()
        logger.info(f"Saved medical ID for user {user.id}")
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
