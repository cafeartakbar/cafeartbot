import os
import json
import logging
from datetime import datetime
from pathlib import Path
from functools import wraps
from telegram import (
    Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
)
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters,
    ConversationHandler, CallbackContext
)
from apscheduler.schedulers.background import BackgroundScheduler
from openpyxl import Workbook

# ---------- تنظیمات ----------
TOKEN = "8289712726:AAGOUkkI6b5uItEjPlRin8XGhuc9fd4E8e0"
DATA_FILE = "data.json"
EXPORT_DIR = Path(r"C:/CafeData/ShoppingLists/")
LOGO_PATH = "logo.png"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_DATA = {
    "daily_items": [],
    "monthly_items": [],
    "shopping_list": [],
    "purchases": [],
    "reminder": {"time": "08:00", "enabled": False}
}
VALID_UNITS = ["تعداد", "گرم", "کیلوگرم"]

# ---------- ذخیره / بارگذاری ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA.copy()
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- کیبوردها ----------
def main_menu_keyboard():
    keys = [
        [InlineKeyboardButton("1️⃣ لیست خرید", callback_data='menu_shopping')],
        [InlineKeyboardButton("2️⃣ آیتم‌های روزانه", callback_data='menu_daily')],
        [InlineKeyboardButton("3️⃣ آیتم‌های ماهانه", callback_data='menu_monthly')],
        [InlineKeyboardButton("4️⃣ خروجی اکسل", callback_data='menu_export')],
        [InlineKeyboardButton("5️⃣ تنظیمات ⚙️", callback_data='menu_settings')]
    ]
    return InlineKeyboardMarkup(keys)

def back_button_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton('🔙 بازگشت به منو', callback_data='back_main')]])

# ---------- زمان‌بندی ----------
scheduler = BackgroundScheduler()
scheduler.start()

def schedule_jobs(updater, data):
    scheduler.remove_all_jobs()
    if data['reminder']['enabled']:
        hh, mm = map(int, data['reminder']['time'].split(':'))

        def job_send_reminder():
            logger.info(f"ارسال یادآور خرید ({hh}:{mm})")

        scheduler.add_job(job_send_reminder, 'cron', hour=hh, minute=mm, id='daily_reminder')

# ---------- خروجی اکسل ----------
def export_to_excel(shopping_list):
    if not shopping_list:
        return None
    now = datetime.now()
    filename = f"ShoppingList-{now.month}-{now.year}.xlsx"
    filepath = EXPORT_DIR / filename
    wb = Workbook()
    ws = wb.active
    ws.append(["کد کالا", "نام کالا", "واحد", "نرخ"])
    for item in shopping_list:
        ws.append([item.get('code'), item.get('name'), item.get('unit'), item.get('rate')])
    wb.save(filepath)
    return str(filepath)

# ---------- شروع ----------
def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, 'rb') as f:
            context.bot.send_photo(chat_id=chat_id, photo=f,
                                   caption="به ربات مدیریت خرید کافه خوش آمدی! 👋",
                                   reply_markup=main_menu_keyboard())
    else:
        update.message.reply_text("به ربات مدیریت خرید کافه خوش آمدی! 👋",
                                  reply_markup=main_menu_keyboard())

# ---------- منو ----------
def menu_router(update: Update, context: CallbackContext):
    query = update.callback_query
    data = load_data()
    query.answer()
    if query.data == 'menu_shopping':
        return show_shopping_list(query)
    if query.data == 'menu_daily':
        return show_items_list(query, 'daily')
    if query.data == 'menu_monthly':
        return show_items_list(query, 'monthly')
    if query.data == 'menu_export':
        return export_file(query)
    if query.data == 'menu_settings':
        return show_settings_menu(query)
    if query.data == 'back_main':
        query.edit_message_text('🏠 منوی اصلی:', reply_markup=main_menu_keyboard())

# ---------- لیست خرید ----------
def show_shopping_list(query):
    data = load_data()
    sl = data['shopping_list']
    if not sl:
        query.edit_message_text("🛒 لیست خرید خالی است.", reply_markup=main_menu_keyboard())
        return
    keys = [[InlineKeyboardButton(item['name'], callback_data=f"done_{i}")]
            for i, item in enumerate(sl)]
    keys.append([InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')])
    query.edit_message_text("🛒 لیست خرید:", reply_markup=InlineKeyboardMarkup(keys))

def shopping_item_done(update: Update, context: CallbackContext):
    query = update.callback_query
    idx = int(query.data.split('_')[1])
    data = load_data()
    try:
        item = data['shopping_list'].pop(idx)
        data['purchases'].append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            **item
        })
        save_data(data)
        query.edit_message_text(f"✅ '{item['name']}' خرید شد.", reply_markup=main_menu_keyboard())
    except:
        query.edit_message_text("⚠️ خطا در حذف آیتم.", reply_markup=main_menu_keyboard())

# ---------- آیتم‌ها ----------
def show_items_list(query, which):
    data = load_data()
    key = 'daily_items' if which == 'daily' else 'monthly_items'
    items = data[key]
    if not items:
        query.edit_message_text("لیست خالی است.", reply_markup=back_button_keyboard())
        return
    keys = [[InlineKeyboardButton(it['name'], callback_data=f"add_{which}_{i}")]
            for i, it in enumerate(items)]
    keys.append([InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')])
    query.edit_message_text(f"📋 آیتم‌های { 'روزانه' if which=='daily' else 'ماهیانه' }",
                            reply_markup=InlineKeyboardMarkup(keys))

def add_item_to_shopping(update: Update, context: CallbackContext):
    query = update.callback_query
    _, which, idx = query.data.split('_')
    data = load_data()
    item = data['daily_items' if which == 'daily' else 'monthly_items'][int(idx)]
    data['shopping_list'].append(item)
    save_data(data)
    query.edit_message_text(f"➕ '{item['name']}' اضافه شد.", reply_markup=back_button_keyboard())

# ---------- تنظیمات ----------
def show_settings_menu(query):
    keys = [
        [InlineKeyboardButton("✳️ افزودن آیتم روزانه", callback_data='add_daily_manual')],
        [InlineKeyboardButton("✳️ افزودن آیتم ماهانه", callback_data='add_monthly_manual')],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')]
    ]
    query.edit_message_text("⚙️ تنظیمات:", reply_markup=InlineKeyboardMarkup(keys))

# ---------- خروجی ----------
def export_file(query):
    data = load_data()
    path = export_to_excel(data['shopping_list'])
    if path:
        query.edit_message_text(f"✅ فایل ساخته شد:\n{path}", reply_markup=back_button_keyboard())
    else:
        query.edit_message_text("⚠️ لیست خرید خالی بود.", reply_markup=back_button_keyboard())

# ---------- مسیریابی ----------
def callback_dispatcher(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    if data.startswith('menu_') or data == 'back_main':
        return menu_router(update, context)
    if data.startswith('done_'):
        return shopping_item_done(update, context)
    if data.startswith('add_daily_') or data.startswith('add_monthly_'):
        return add_item_to_shopping(update, context)

# ---------- اجرا ----------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CallbackQueryHandler(callback_dispatcher))
    schedule_jobs(updater, load_data())
    updater.start_polling()
    logger.info("Bot started.")
    updater.idle()

if __name__ == "__main__":
    main()
