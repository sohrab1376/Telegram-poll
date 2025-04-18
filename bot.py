
عذرخواهی می‌کنم بابت این اشتباه. شما درست اشاره کردید که آیدی ادمین در کد قبلی هاردکد شده بود (`admin_id = 130742264`) و باید به صورت متغیر محیطی یا به روش امن‌تری مدیریت شود. در کد اصلاح‌شده زیر، آیدی ادمین را به صورت متغیر محیطی (`ADMIN_ID`) به کد اضافه کرده‌ام تا از هاردکد کردن جلوگیری شود و امنیت بیشتری داشته باشد. همچنین، سایر تغییرات قبلی (مثل استفاده از `aiosqlite` و لاگ‌های پیشرفته) حفظ شده‌اند.

---

### **تغییرات جدید**
1. **مدیریت آیدی ادمین**:
   - آیدی ادمین حالا از متغیر محیطی `ADMIN_ID` خوانده می‌شود.
   - اگر `ADMIN_ID` تنظیم نشده باشد، برنامه با خطا متوقف می‌شود و لاگ مربوطه ثبت می‌شود.
2. **بررسی‌های اضافی**:
   - اضافه کردن لاگ برای بررسی مقدار `ADMIN_ID` در زمان اجرا.
   - اطمینان از اینکه فقط ادمین به دستور `/results` دسترسی دارد.

---

### **کد کامل اصلاح‌شده**
```python
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
import aiosqlite
from aiohttp import web

# تنظیمات لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# خواندن توکن، پورت و آیدی ادمین
TOKEN = os.getenv('TOKEN')
PORT = int(os.getenv('PORT', '10000'))
ADMIN_ID = os.getenv('ADMIN_ID')
WEBHOOK_URL = "https://telegram-poll.onrender.com/"

# بررسی وجود آیدی ادمین
if not ADMIN_ID:
    logger.error("No ADMIN_ID provided in environment variables")
    raise ValueError("ADMIN_ID environment variable is required")
else:
    logger.info(f"Admin ID set to {ADMIN_ID}")

# اتصال به دیتابیس به صورت غیرهمزمان
async def get_db():
    db = await aiosqlite.connect('survey.db')
    db.row_factory = aiosqlite.Row
    return db

# ایجاد جدول
async def init_db():
    async with await get_db() as db:
        await db.execute('''
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
            await db.execute('ALTER TABLE responses ADD COLUMN completed INTEGER DEFAULT 0')
        except aiosqlite.OperationalError:
            pass
        await db.commit()

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

# گزینه‌ها
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

# اعتبارسنجی تعداد سوالات و گزینه‌ها
if len(QUESTIONS) != len(OPTIONS):
    logger.error("Mismatch between QUESTIONS and OPTIONS lengths")
    raise ValueError("Number of questions and options must match")

# بررسی تکمیل نظرسنجی
async def check_completed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    async with await get_db() as db:
        async with db.execute('SELECT completed FROM responses WHERE user_id = ?', (user.id,)) as cursor:
            result = await cursor.fetchone()
            if result and result['completed'] == 1:
                await update.effective_message.reply_text('شما قبلاً در این نظرسنجی شرکت کرده‌اید.')
                logger.info(f"User {user.id} blocked due to completed survey")
                return True
    return False

# شروع نظرسنجی
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await check_completed(update, context):
        return
    user = update.message.from_user
    async with await get_db() as db:
        async with db.execute('SELECT * FROM responses WHERE user_id = ?', (user.id,)) as cursor:
            if not await cursor.fetchone():
                await db.execute('INSERT OR IGNORE INTO responses (user_id, username) VALUES (?, ?)', (user.id, user.username))
                await db.commit()
    context.user_data['question_index'] = 0
    logger.info(f"Starting survey for user {user.id}")
    await ask_question(update, context)

# ارسال سوال
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await check_completed(update, context):
        return
    index = context.user_data.get('question_index', 0)
    logger.info(f"Preparing to ask question {index} for user {update.effective_user.id}")
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
            logger.info(f"Question {index} sent to user {update.effective_user.id}")
        except Exception as e:
            logger.error(f"Error sending question {index} to user {update.effective_user.id}: {e}")
    else:
        logger.info(f"Reached end of questions for user {update.effective_user.id}")
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

    logger.info(f"Processing response for question {index} from user {user.id}: {answer}")

    async with await get_db() as db:
        await db.execute('INSERT OR IGNORE INTO responses (user_id, username) VALUES (?, ?)', (user.id, user.username))
        await db.execute(f'UPDATE responses SET q{index+1} = ? WHERE user_id = ?', (answer, user.id))
        await db.commit()

    context.user_data['question_index'] = index + 1
    logger.info(f"Set question_index to {context.user_data['question_index']} for user {user.id}")
    if context.user_data['question_index'] >= len(QUESTIONS):
        logger.info(f"User {user.id} reached end of questions")
    await ask_question(update, context)

# دریافت شماره نظام پزشکی
async def handle_medical_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    if await check_completed(update, context):
        return
    if context.user_data.get('question_index', 0) == len(QUESTIONS):
        medical_id = update.message.text
        async with await get_db() as db:
            await db.execute('UPDATE responses SET medical_id = ?, completed = 1 WHERE user_id = ?', (medical_id, user.id))
            await db.commit()
        await update.message.reply_text('نظرات شما ثبت شد، با تشکر از همکاری شما')
        logger.info(f"Medical ID saved for user {user.id}")
    else:
        await update.message.reply_text('لطفاً ابتدا نظرسنجی را تکمیل کنید.')
        logger.warning(f"User {user.id} tried to submit medical ID before completing survey")

# نمایش نتایج
async def results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    if str(user.id) != ADMIN_ID:
        await update.message.reply_text('شما قبلاً در این نظرسنجی شرکت کرده‌اید.' if await check_completed(update, context) else 'فقط ادمین می‌تونه نتایج رو ببینه!')
        logger.warning(f"User {user.id} attempted to access results without admin privileges")
        return

    async with await get_db() as db:
        async with db.execute('SELECT * FROM responses') as cursor:
            rows = await cursor.fetchall()
            if not rows:
                await update.message.reply_text("هیچ پاسخی ثبت نشده.")
                return

            response_text = "نتایج نظرسنجی:\n"
            for row in rows:
                response_text += f"کاربر: @{row['username']} (ID: {row['user_id']})\n"
                for i in range(1, 11):
                    response_text += f"سوال {i}: {row[f'q{i}']}\n"
                response_text += f"شماره نظام پزشکی: {row['medical_id']}\n\n"
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

    # مقداردهی اولیه دیتابیس
    await init_db()

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
        await app.bot
