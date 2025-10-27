import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ===============================
# دریافت توکن از تنظیمات Render
# ===============================
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise RuntimeError("❌ Bot token not found! Please set TOKEN in Render Environment Variables.")

# ===============================
# دستورات اصلی ربات
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛒 لیست خرید", callback_data="shopping")],
        [InlineKeyboardButton("📊 آمار ماهانه", callback_data="stats")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("سلام 👋 به ربات مدیریت خرید کافه خوش اومدی!", reply_markup=reply_markup)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "shopping":
        await query.edit_message_text("🛒 لیست خرید هنوز در حال توسعه است.")
    elif data == "stats":
        await query.edit_message_text("📊 آمار ماهانه به‌زودی فعال می‌شود.")
    elif data == "settings":
        await query.edit_message_text("⚙️ بخش تنظیمات در حال آماده‌سازی است.")

# ===============================
# راه‌اندازی ربات
# ===============================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_menu))
    app.run_polling()

if __name__ == "__main__":
    main()
