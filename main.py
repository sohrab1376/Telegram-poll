
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
import json
import os

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
user_answers = {}
awaiting_medical_number = {}

def save_response(user_id, username, medical_number, answers):
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_answers[user_id] = {}

    keyboard = []
    for i, q in enumerate(QUESTIONS):
        row = [InlineKeyboardButton(text=opt, callback_data=f"{i}:{opt}") for opt in q["options"]]
        keyboard.append([InlineKeyboardButton(f"--- {q['text']} ---", callback_data="ignore")])
        keyboard.extend([[b] for b in row])
        keyboard.append([InlineKeyboardButton(" ", callback_data="ignore")])

    keyboard.append([InlineKeyboardButton("ثبت پاسخ‌ها", callback_data="submit")])
    await update.message.reply_text("لطفاً به سوالات زیر پاسخ دهید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or "ندارد"
    data = query.data

    if data == "submit":
        answers = user_answers.get(user_id, {})
        if len(answers) < len(QUESTIONS):
            await query.message.reply_text("لطفاً به **همه سوالات** پاسخ دهید.")
        else:
            awaiting_medical_number[user_id] = True
            await query.message.reply_text("لطفاً برای ثبت نهایی، شماره نظام پزشکی خود را وارد کنید:")
    elif ":" in data:
        q_index, answer = data.split(":", 1)
        user_answers[user_id][int(q_index)] = answer
        await query.message.reply_text(f"پاسخ شما به سوال {int(q_index)+1} ثبت شد: {answer}")

async def handle_medical_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if awaiting_medical_number.get(user_id):
        context.user_data["medical_number"] = update.message.text
        keyboard = [[InlineKeyboardButton("تایید و ثبت نهایی", callback_data="final_submit")]]
        await update.message.reply_text("شماره ثبت شد. برای تایید نهایی، روی دکمه زیر بزنید:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        awaiting_medical_number[user_id] = False

async def final_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    username = query.from_user.username or "ندارد"
    answers = user_answers.get(user_id, {})
    medical_number = context.user_data.get("medical_number", "ثبت نشده")

    save_response(user_id, username, medical_number, answers)
    await query.message.reply_text("نظرات شما ثبت شد. با تشکر از همکاری شما")

async def get_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    message = "نتایج ثبت‌شده:"
    for uid, info in data.items():
        message += f"کاربر: {info['username']} | ID: {uid} | نظام پزشکی: {info['medical_number']}
"
        for i, a in enumerate(info["answers"].values()):
            message += f"سوال {i+1}: {a}
"
        message += "------
"

    await update.message.reply_text(message)

if __name__ == "__main__":
    import os
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("results", get_results))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(final_submit, pattern="final_submit"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_medical_number))

    print("Bot is running...")
    app.run_polling()
