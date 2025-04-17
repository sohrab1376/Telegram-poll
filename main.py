from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
import json
import os
import logging
import re

# تنظیم لاگینگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

QUESTIONS = [
    {
        "text": "سوال ۱_آیا با روند پرداختی های فعلی، دستیابی به اهداف زندگی خود را ممکن می‌دانید؟",
        "options": ["بله", "خیر"]
    },
    {
        "text": "سوال ۲_آیا روند پرداختی درمانگاه‌ها را نامناسب می‌دانید و حاضر به همکاری هستید؟",
        "options": ["بله", "خیر"]
    },
    {
        "text": "سوال ۳_در حال حاضر مشغول کدام هستید؟",
        "options": ["طرح اجباری", "خدمت اجباری", "شروع نکردم", "قبلاً گذرانده‌ام"]
    },
    {
        "text": "سوال ۴_آیا پروانه طبابت فعال، موقت یا نامه عدم نیاز دارید؟",
        "options": ["بله", "خیر"]
    },
    {
        "text": "سوال ۵_آیا طی ماه گذشته در درمانگاهی کار کرده‌اید؟",
        "options": ["خصوصی <10 شیفت", "خصوصی >10 شیفت", "سایر <10", "سایر >10", "خیر"]
    },
    {
        "text": "سوال ۶_آیا با مطالبه کف پرداختی ۴۰۰ت + درصدها موافق هستید؟",
        "options": ["بله", "خیر"]
    },
    {
        "text": "سوال ۷_آیا با قطع کامل همکاری تا رسیدن به پرداختی مناسب موافقید؟",
        "options": ["بله", "خیر"]
    },
    {
        "text": "سوال ۸_آیا با برنداشتن شیفت در روزهای مشخص موافقید؟",
        "options": ["بله", "خیر"]
    },
    {
        "text": "سوال ۹_آیا با قطع همکاری با درمانگاه‌های بدحساب موافقید؟",
        "options": ["بله", "خیر"]
    },
    {
        "text": "سوال ۱۰_آیا مجبور به پر کردن شیفت‌ها تحت هر شرایطی هستید؟",
        "options": ["بله", "خیر"]
    },
]

RESPONSES_FILE = "responses.json"

def save_response(user_id, username, medical_number, answers):
    try:
        if os.path.exists(RESPONSES_FILE):
            with open(RESPONSES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}

        data[str(user_id)] = {
            "username": username,
            "medical_number": medical_number,
            "answers": answers
        }

        with open(RESPONSES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving response: {e}")
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data["answers"] = {}  # ذخیره پاسخ‌ها در context.user_data
    context.user_data["awaiting_medical_number"] = False

    keyboard = []
    for i, q in enumerate(QUESTIONS):
        keyboard.append([InlineKeyboardButton(f"📌 {q['text']}", callback_data="ignore")])
        row = [InlineKeyboardButton(opt, callback_data=f"{i}:{opt}") for opt in q["options"]]
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("ثبت پاسخ‌ها", callback_data="submit")])
    await update.message.reply_text("لطفاً به سوالات زیر پاسخ دهید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or "ندارد"
    data = query.data

    if data == "ignore":
        return

    if data == "submit":
        answers = context.user_data.get("answers", {})
        if len(answers) < len(QUESTIONS):
            await query.message.reply_text("لطفاً به **همه سوالات** پاسخ دهید.")
        else:
            context.user_data["awaiting_medical_number"] = True
            await query.message.reply_text("لطفاً شماره نظام پزشکی خود را وارد کنید (فقط عدد):")
    elif ":" in data:
        q_index, answer = data.split(":", 1)
        q_index = int(q_index)
        context.user_data["answers"][q_index] = answer

        # به‌روزرسانی پیام اصلی برای نمایش پاسخ‌های انتخاب‌شده
        keyboard = []
        for i, q in enumerate(QUESTIONS):
            keyboard.append([InlineKeyboardButton(f"📌 {q['text']}", callback_data="ignore")])
            row = []
            for opt in q["options"]:
                prefix = "✅ " if context.user_data["answers"].get(i) == opt else ""
                row.append(InlineKeyboardButton(f"{prefix}{opt}", callback_data=f"{i}:{opt}"))
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("ثبت پاسخ‌ها", callback_data="submit")])
        await query.message.edit_text("لطفاً به سوالات زیر پاسخ دهید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_medical_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.user_data.get("awaiting_medical_number", False):
        return

    medical_number = update.message.text.strip()
    # اعتبارسنجی ساده شماره نظام پزشکی (مثلاً فقط عدد باشد)
    if not re.match(r"^\d+$", medical_number):
        await update.message.reply_text("لطفاً شماره نظام پزشکی معتبر (فقط عدد) وارد کنید:")
        return

    context.user_data["medical_number"] = medical_number
    keyboard = [[InlineKeyboardButton("تایید و ثبت نهایی", callback_data="final_submit")]]
    await update.message.reply_text(f"شماره نظام پزشکی: {medical_number}\nبرای تایید نهایی، روی دکمه زیر بزنید:",
                                   reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["awaiting_medical_number"] = False

async def final_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    username = query.from_user.username or "ندارد"
    answers = context.user_data.get("answers", {})
    medical_number = context.user_data.get("medical_number", "ثبت نشده")

    if len(answers) < len(QUESTIONS):
        await query.message.reply_text("خطا: پاسخ‌ها کامل نیستند.")
        return

    try:
        save_response(user_id, username, medical_number, answers)
        await query.message.reply_text("نظرات شما ثبت شد. با تشکر از همکاری شما!")
        # پاک‌سازی داده‌های کاربر
        context.user_data.clear()
    except Exception as e:
        logger.error(f"Error in final_submit: {e}")
        await query.message.reply_text("خطایی رخ داد. لطفاً دوباره تلاش کنید.")

async def get_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        admin_ids = [admin.user.id for admin in chat_admins]

        if update.effective_user.id not in admin_ids:
            await update.message.reply_text("فقط ادمین‌ها می‌توانند نتیجه را ببینند.")
            return

        if not os.path.exists(RESPONSES_FILE):
            await update.message.reply_text("هنوز پاسخی ثبت نشده.")
            return

        with open(RESPONSES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        message = "نتایج ثبت‌شده:\n\n"
        for uid, info in data.items():
            message += f"کاربر: {info['username']} | ID: {uid} | نظام پزشکی: {info['medical_number']}\n"
            for i, a in enumerate(info["answers"].values()):
                message += f"سوال {i+1}: {a}\n"
            message += "------\n"

        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in get_results: {e}")
        await update.message.reply_text("خطایی در نمایش نتایج رخ داد.")

if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.error("BOT_TOKEN is not set.")
        raise ValueError("Please set the BOT_TOKEN environment variable.")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("results", get_results))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(final_submit, pattern="final_submit"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_medical_number))

    logger.info("Bot is running...")
    app.run_polling()
