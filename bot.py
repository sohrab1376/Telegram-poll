
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
from googlesearch import search  # برای جستجوی گوگل

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
    "سوال 1_همکار گرامی آیا با روند پرداختی های فعلی دستیابی به اهداف کوتاه مدت و بلند مدت زندگی خود را در شان یک پزشک ممکن میدانید؟",
    "سوال 2_همکار گرامی آیا روند کنونی پرداختی های درمانگاه ها را نامناسب میدانید و برای اصلاح آن حاضر به همکاری هستید؟",
    "سوال 3_همکار گرامی در حال حاضر مشغول سپری کردن کدام یک از موارد زیر هستید؟",
    "سوال 4_همکار گرامی آیا در حال حاضر پروانه طبابت فعال پروانه موقت و یا نامه عدم نیاز در ساعات غیر اداری در اختیار دارید؟",
    "سوال 5_همکار گرامی آیا طی یک ماهه گذشته در درمانگاهی مشغول به کار بوده اید؟",
    "سوال 6_همکار گرامی آیا با مطالبه کف پرداختی ساعتی 400 ت همراه با 25 درصد خدمات و 50 درصد پروسیژر و یا پرکیس معادل کا حرفه ای درصورت ویزیت میانگین بیشتر از 4 بیمار در ساعت و عدم پذیرش همکاری با نرخ کمتر از این مقدار به صورت علل حساب تا زمان حصول یک فرمول جامع موافق هستید؟",
    "سوال 7_همکار گرامی آیا در صورت تصمیم جمعی مبنی بر قطع کامل هرگونه همکاری با درمانگاهداران و عدم تمدید قرارداد تا حصول پرداختی قابل قبول با این حرکت اعتراضی همراه خواهید بود؟",
    "سوال 8_همکار گرامی آیا در صورت تصمیم جمعی مبنی بر برنداشتن شیفت و خالی گذاشتن و کاور نکردن آن ها فقط در روز های مشخصی از هر ماه با این حرکت اعتراضی همراه خواهید بود؟",
    "سوال 9_همکار گرامی آیا در صورت تصمیم جمعی مبنی بر قطع هرگونه همکاری و عدم تمدید قرارداد با تعداد مشخصی از درمانگاه های بدحساب با این حرکت اعتراضی همراه خواهید بود؟",
    "سوال 10_همکار گرامی آیا مسائل و مشکلات زندگی و یا سایر دلایل شما را مجبور به پر کردن شیفت ها تحت هر شرایطی کرده؟"
]

# گزینه‌های هر سوال (خط 73 اصلاح‌شده)
OPTIONS = [
    [("بله", "yes"), ("خیر", "no")],
    [("بله", "yes"), ("خیر", "no")],
    [("طرح اجباری", "opt1"), ("خدمت اجباری", "opt2"), ("هنوز طرح یا خدمت اجباری را شروع نکردم", "opt3"), ("طرح یا خدمت اجباری را قبلا سپری کردم", "opt4")],
    [("بله", "yes"), ("خیر", "no")],
    [("درمانگاه خصوصی کمتر از 10 شیفت", "opt1"), ("درمانگاه خصوصی بیشتر از 10 شیفت", "opt2"), ("سایر مراکز کمتر از 10 شیفت", "opt3"), ("سایر مراکز بیشتر از 10 شیفت", "opt4"), ("خیر", "opt5")],
    [("بله", "yes"), ("خير", "no")],
    [("بله", "yes"), ("خير", "no")],
    [("بله", "yes"), ("خير", "no")],
    [("بله", "yes"), ("خير", "no")],
    [("بله", "yes"), ("خير", "no")]
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
    context.user_data['responses'] = {}
    context.user_data['question_index'] = 0
    context.user_data['last_message_id'] = None
    context.user_data['medical_id_attempts'] = 0  # مقداردهی اولیه تعداد تلاش‌ها
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
                message = await update.message.reply_text(question, reply_markup=reply_markup)
            else:
                message = await update.callback_query.message.reply_text(question, reply_markup=reply_markup)
            context.user_data['last_message_id'] = message.message_id
            logger.info(f"Sent question {index} to user {user.id} with callback_data: {[f'{index}_{data}' for _, data in options]}, message_id: {message.message_id}")
        except Exception as e:
            logger.error(f"Error sending question {index} to user {user.id}: {e}")
            await (update.message or update.callback_query.message).reply_text("خطایی در ارسال سوال رخ داد. لطفاً دوباره سعی کنید.")
    else:
        logger.info(f"Reached end of questions for user {user.id}, asking for medical ID")
        try:
            if context.user_data.get('last_message_id'):
                await context.bot.delete_message(chat_id=user.id, message_id=context.user_data['last_message_id'])
                logger.info(f"Deleted last question message for user {user.id}, message_id: {context.user_data['last_message_id']}")
        except Exception as e:
            logger.error(f"Failed to delete last question message for user {user.id}: {e}")
        context.user_data['last_message_id'] = None
        await (update.message or update.callback_query.message).reply_text('جهت احراز صلاحیت شرکت در نظرسنجی، احتراما شماره نظام پزشکی خود را وارد نمایید')

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

        for text, cb_data in OPTIONS[index]:
            if cb_data == answer:
                answer_text = text
                break
        else:
            logger.error(f"Invalid callback_data for question {index} from user {user.id}: {answer}")
            await query.message.reply_text(f"گزینه انتخاب‌شده برای سوال {index+1} نامعتبر است. لطفاً یکی از گزینه‌های نمایش‌داده‌شده را انتخاب کنید.")
            return

        context.user_data['responses'][f'q{index+1}'] = answer_text
        logger.info(f"Temporarily saved response for question {index} for user {user.id}: {answer_text}")

        try:
            if context.user_data.get('last_message_id'):
                await context.bot.delete_message(chat_id=user.id, message_id=context.user_data['last_message_id'])
                logger.info(f"Deleted previous question message for user {user.id}, message_id: {context.user_data['last_message_id']}")
        except Exception as e:
            logger.error(f"Failed to delete previous question message for user {user.id}: {e}")

        context.user_data['question_index'] = index + 1
        logger.info(f"Updated question_index to {context.user_data['question_index']} for user {user.id}")

        await ask_question(update, context)
        logger.info(f"Triggered ask_question for index {context.user_data['question_index']} for user {user.id}")
    except Exception as e:
        logger.error(f"Error in handle_response for user {user.id}: {e}")
        await query.message.reply_text("خطایی رخ داد. لطفاً دوباره سعی کنید.")

# دریافت شماره نظام پزشکی و تأیید با فرصت‌های اضافی
async def handle_medical_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    if await check_completed(update, context):
        return
    if context.user_data.get('question_index', 0) == len(QUESTIONS):
        medical_id = update.message.text.strip()
        responses = context.user_data.get('responses', {})

        if len(responses) != len(QUESTIONS):
            await update.message.reply_text('لطفاً همه سوالات را پاسخ دهید.')
            return

        # افزایش تعداد تلاش‌ها
        context.user_data['medical_id_attempts'] = context.user_data.get('medical_id_attempts', 0) + 1
        attempts = context.user_data['medical_id_attempts']
        logger.info(f"Attempt {attempts} for medical ID by user {user.id}")

        # جستجوی شماره نظام پزشکی در گوگل
        query = f"{medical_id} site:irimc.org"
        try:
            search_results = list(search(query, num_results=1))
            if search_results and "membersearch.irimc.org" in search_results[0]:
                is_valid = True
            else:
                is_valid = False
                logger.info(f"No valid search results found for medical ID {medical_id} for user {user.id}")
        except Exception as e:
            logger.error(f"Error searching medical ID {medical_id} for user {user.id}: {e}")
            is_valid = False

        if not is_valid:
            if attempts < 3:
                remaining_attempts = 3 - attempts
                await update.message.reply_text(
                    f'شماره نظام پزشکی واردشده معتبر نیست یا با نام دکتری مرتبط نیست. '
                    f'لطفاً دوباره بررسی کنید. ({remaining_attempts} فرصت باقی‌مانده)'
                )
                return
            else:
                # بعد از 3 تلاش ناموفق، نظرسنجی کنسل می‌شه
                await update.message.reply_text(
                    'شما 3 بار شماره نظام پزشکی نامعتبر وارد کردید. نظرسنجی کنسل شد. '
                    'لطفاً با دستور /start دوباره شروع کنید.'
                )
                context.user_data['responses'] = {}
                context.user_data['question_index'] = 0
                context.user_data['medical_id_attempts'] = 0
                logger.info(f"Survey cancelled for user {user.id} after 3 invalid medical ID attempts")
                return

        # اگر شماره معتبر بود، ذخیره پاسخ‌ها
        try:
            cursor.execute('INSERT OR IGNORE INTO responses (user_id, username) VALUES (?, ?)', (user.id, user.username))
            cursor.execute('''
                UPDATE responses SET
                q1 = ?, q2 = ?, q3 = ?, q4 = ?, q5 = ?,
                q6 = ?, q7 = ?, q8 = ?, q9 = ?, q10 = ?,
                medical_id = ?, completed = 1
                WHERE user_id = ?
            ''', (
                responses.get('q1'), responses.get('q2'), responses.get('q3'), responses.get('q4'), responses.get('q5'),
                responses.get('q6'), responses.get('q7'), responses.get('q8'), responses.get('q9'), responses.get('q10'),
                medical_id, user.id
            ))
            conn.commit()
            logger.info(f"Saved all responses and medical ID for user {user.id}")

            # ارسال نتایج به ادمین
            admin_id = 130742264
            result_message = f"نظرسنجی جدید تکمیل شد:\nکاربر: @{user.username} (ID: {user.id})\n"
            for i in range(1, 11):
                result_message += f"سوال {i}: {responses.get(f'q{i}')}\n"
            result_message += f"شماره نظام پزشکی: {medical_id}"

            try:
                await context.bot.send_message(chat_id=admin_id, text=result_message)
                logger.info(f"Sent survey results to admin for user {user.id}")
            except Exception as e:
                logger.error(f"Failed to send results to admin for user {user.id}: {e}")

            await update.message.reply_text('نظرات شما ثبت شد، با تشکر از همکاری شما')
            context.user_data['responses'] = {}
            context.user_data['medical_id_attempts'] = 0  # ریست تعداد تلاش‌ها
        except Exception as e:
            logger.error(f"Error saving responses for user {user.id}: {e}")
            await update.message.reply_text('خطایی در ثبت پاسخ‌ها رخ داد. لطفاً دوباره سعی کنید.')
    else:
        await update.message.reply_text('لطفاً ابتدا نظرسنجی را تکمیل کنید.')

# نمایش گزارش خلاصه نتایج
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = 130742264
    user = update.message.from_user
    if user.id != admin_id:
        await update.message.reply_text('فقط ادمین می‌تونه گزارش رو ببینه!')
        return

    cursor.execute('SELECT COUNT(*) FROM responses WHERE completed = 1')
    total_responses = cursor.fetchone()[0]
    if total_responses == 0:
        await update.message.reply_text("هیچ پاسخی ثبت نشده.")
        return

    response_text = f"گزارش خلاصه نظرسنجی:\nتعداد پاسخ‌دهندگان: {total_responses}\n\n"
    for q_index in range(len(QUESTIONS)):
        response_text += f"سوال {q_index+1}:\n"
        cursor.execute(f'SELECT q{q_index+1}, COUNT(*) FROM responses WHERE completed = 1 GROUP BY q{q_index+1}')
        answers = cursor.fetchall()
        for answer, count in answers:
            if answer:
                percentage = (count / total_responses) * 100
                response_text += f"- {answer}: {percentage:.1f}%\n"
        response_text += "\n"

    await update.message.reply_text(response_text)

# نمایش نتایج کامل
async def results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = 130742264
    user = update.message.from_user
    if user.id != admin_id:
        await update.message.reply_text('شما قبلاً در این نظرسنجی شرکت کرده‌اید.' if await check_completed(update, context) else 'فقط ادمین می‌تونه نتایج رو ببینه!')
        return

    cursor.execute('SELECT * FROM responses WHERE completed = 1')
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
    app.add_handler(CommandHandler("summary", summary))

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
