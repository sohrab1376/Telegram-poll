
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
import asyncio

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

# لیست سوالات (با علامت سوال)
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

# گزینه‌های هر سوال (نمایش فارسی، callback_data لاتین)
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

# دریافت شماره نظام پزشکی و ذخیره پاسخ‌ها
async def handle_medical_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    if await check_completed(update, context):
        return
    if context.user_data.get('question_index', 0) == len(QUESTIONS):
        medical_id = update.message.text
        responses = context.user_data.get('responses', {})

        if len(responses) != len(QUESTIONS):
            await update.message.reply_text('لطفاً همه سوالات را پاسخ دهید.')
            return

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

# تابع اضافه کردن اعضا به گروه
async def add_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = 130742264
    user = update.message.from_user
    if user.id != admin_id:
        await update.message.reply_text('فقط ادمین می‌تونه این دستور رو اجرا کنه!')
        return

    GROUP_INVITE_LINK = "https://t.me/+E6vJ1Y537-ljOGU0"
    INVITE_MESSAGE = "سلام همکار گرامی!\nبه دلیل محدودیت‌های حریم خصوصی، به صورت خودکار به گروه اضافه نشدید. احتراما با استفاده از لینک زیر به گروه 'پزشکان خوزستان(تایید شده)' بپیوندید:\n{GROUP_INVITE_LINK}\nبا تشکر!"
    USER_IDS = [
        40210485, 40603389, 41237512, 42274915, 45856546,
        70548107, 74655024, 74706805, 76974160, 82322616,
        86217516, 88528693, 90406110, 90973458, 91796213,
        93717917, 102016148, 102717046, 103041834, 107575794,
        125988236, 126033025, 127204127, 128211362, 130742264,
        141642888, 154577520, 156806669, 169145975, 171383552,
        184281552, 201998730, 224679292, 237109372, 248095045,
        248376711, 263571873, 268630776, 294024995, 308904499,
        314796797, 347797102, 359578115, 375090950, 382719543,
        386530940, 420286813, 421862790, 425425101, 437390703,
        446998292, 489556505, 489760950, 630870805, 728780186,
        743000210, 871370289, 1269929448, 1707766882, 1787580725,
        1838813771, 5734586072, 5909606644, 6053140393, 6091891336,
        6438754301, 6704827782, 7048291530, 95419818, 125991359,
        378840533, 389958329, 429736122, 455688480, 102417629,
        94070512, 5415129022, 363063803, 93314994, 876872032,
        33059999, 397669064, 876872032, 44986829, 267908416,
        71899260, 66252143, 172783172, 2025484113, 5136365966,
        151156108, 440014443, 226393572, 108522377, 322740548,
        279913071, 133636003, 766873645, 144900576, 90541482,
        124348276, 167757002, 1096968283, 674529726, 83203274,
        743375673, 247422725, 613974131, 851620982, 152495225,
        5432539473, 144013104, 154158526, 33187913, 39497007,
        190063287, 610757050, 105547525, 457534629, 5789627096,
        60611363, 207095500, 176873105, 392946123
    ]

    chat_id = -1002548262598  # آی‌دی گروه که ازت گرفتم
    success_count = 0
    failed_count = 0

    try:
        for user_id in USER_IDS:
            try:
                await context.bot.add_chat_member(chat_id=chat_id, user_id=user_id)
                success_count += 1
                logger.info(f"Successfully added user {user_id} to group")
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to add user {user_id} to group: {e}")
                invite_msg = INVITE_MESSAGE.format(GROUP_INVITE_LINK=GROUP_INVITE_LINK)
                try:
                    await context.bot.send_message(chat_id=user_id, text=invite_msg)
                    logger.info(f"Sent invite link to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send invite link to user {user_id}: {e}")
            await asyncio.sleep(1)  # تاخیر ۱ ثانیه‌ای بین هر ادد کردن برای جلوگیری از محدودیت تلگرام
        await update.message.reply_text(f"عملیات تکمیل شد. {success_count} نفر با موفقیت اضافه شدند، {failed_count} نفر به دلیل محدودیت‌های حریم خصوصی نیاز به لینک دعوت دارند.")
    except Exception as e:
        logger.error(f"Error in add_members: {e}")
        await update.message.reply_text("خطایی در فرآیند اضافه کردن اعضا رخ داد.")

# تابع دریافت لیست اعضای گروه
async def get_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = 130742264
    user = update.message.from_user
    if user.id != admin_id:
        await update.message.reply_text('فقط ادمین می‌تونه این دستور رو اجرا کنه!')
        return

    chat_id = -1002548262598  # آی‌دی گروه که ازت گرفتم
    try:
        # گرفتن تعداد کل اعضا
        member_count = await context.bot.get_chat_member_count(chat_id=chat_id)
        response_text = f"تعداد کل اعضای گروه: {member_count}\n\nلیست آی‌دی‌ها:\n"

        # گرفتن لیست اعضا با استفاده از offset
        offset = 0
        limit = 200  # حداکثر تعداد در هر درخواست
        all_members = []
        while True:
            members = await context.bot.get_chat_members(chat_id=chat_id, offset=offset)
            if not members:
                break
            all_members.extend(members)
            offset += len(members)
            if len(members) < limit:
                break

        # ساخت لیست آی‌دی‌ها
        for member in all_members:
            user_id = member.user.id
            username = member.user.username if member.user.username else f"User_{user_id}"
            response_text += f"ID: {user_id} - @{username}\n"
            if len(response_text) > 3000:
                await update.message.reply_text(response_text)
                response_text = ""

        if response_text:
            await update.message.reply_text(response_text)
    except Exception as e:
        logger.error(f"Error in get_members: {e}")
        await update.message.reply_text("خطایی در دریافت لیست اعضای گروه رخ داد.")

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
    app.add_handler(CommandHandler("addmembers", add_members))
    app.add_handler(CommandHandler("getmembers", get_members))

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
