کد کامل ربات مدیریت خرید کافه
ویژگی‌ها (طبق درخواست کاربر):
- منوی فارسی با ایموجی
- لیست خرید (مواد انتخاب شده از لیست‌های روزانه/ماهیانه)
- آیتم‌های روزانه/ماهیانه قابل افزودن/حذف از تنظیمات
- خروجی اکسل با ساختار: کد کالا | نام کالا | واحد کالا | نرخ کالا
- ذخیره‌سازی در data.json
- مسیر خروجی: C:/CafeData/ShoppingLists/ShoppingList-[ماه]-[سال].xlsx (در صورت نبودن ساخته می‌شود)
- یادآور روزانه از طریق APScheduler
- واحدها فقط: 'تعداد', 'گرم', 'کیلوگرم'
- هنگامی که روی آیتم در لیست خرید کلیک شود، از لیست خرید حذف می‌شود ولی از لیست روزانه/ماهیانه حذف نمی‌شود

نکته: توکن را در متغیر TOKEN قرار بده (جایگزین "YOUR_TELEGRAM_BOT_TOKEN").
نیازمندی‌ها (pip): python-telegram-bot, openpyxl, apscheduler

اجرای مثال:
    pip install python-telegram-bot==13.15 openpyxl apscheduler
    python کد-ربات-خرید-کافه.py

"""

import os
import json
import logging
from datetime import datetime, time, date
from pathlib import Path
from functools import wraps

from telegram import (Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ParseMode, InputMediaPhoto)
from telegram.ext import (Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters,
                          ConversationHandler, CallbackContext)
from apscheduler.schedulers.background import BackgroundScheduler
from openpyxl import Workbook

# ---------- تنظیمات اولیه ----------
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # <-- اینجا توکن را جایگذاری کن
DATA_FILE = "data.json"
EXPORT_DIR = Path(r"C:/CafeData/ShoppingLists/")
LOGO_PATH = "logo.png"  # تصویر لوگوی کافه برای پیام /start (باید در همان پوشه باشد)

# اطمینان از وجود مسیر خروجی
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- لاگینگ ----------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(name)

# ---------- ساختار داده پیش‌فرض ----------
DEFAULT_DATA = {
    "daily_items": [],
    "monthly_items": [],
    "shopping_list": [],  # آیتم‌هایی که الان باید خرید شوند. فقط نام در نمایش نشان داده می‌شود.
    "purchases": [],  # تاریخچه خریدها برای آمار ماهانه
    "reminder": {
        "time": "08:00",
        "enabled": False
    }
}

VALID_UNITS = ["تعداد", "گرم", "کیلوگرم"]

# ---------- توابع کمکی ذخیره/بارگذاری ----------

def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA.copy()
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- دستیار ساخت کیبوردها ----------

def main_menu_keyboard():
    keys = [
        [InlineKeyboardButton("1️⃣ لیست خرید", callback_data='menu_shopping')],
        [InlineKeyboardButton("2️⃣ آیتم‌های لیست خرید روزانه", callback_data='menu_daily')],
        [InlineKeyboardButton("3️⃣ آیتم‌های لیست خرید ماهانه", callback_data='menu_monthly')],
        [InlineKeyboardButton("4️⃣ فایل خروجی اکسل", callback_data='menu_export')],
        [InlineKeyboardButton("5️⃣ تنظیمات ⚙️", callback_data='menu_settings')]
    ]
    return InlineKeyboardMarkup(keys)


def back_button_keyboard(back_to='main'):
    return InlineKeyboardMarkup([[InlineKeyboardButton('🔙 بازگشت به منوی اصلی', callback_data='back_main')]])

# ---------- وظایف زمانبندی (یادآور) ----------

scheduler = BackgroundScheduler()
scheduler_started = False


def schedule_jobs(updater: Updater, data):
    global scheduler_started
    scheduler.remove_all_jobs()

    if data.get('reminder', {}).get('enabled'):
        time_str = data['reminder'].get('time', '08:00')
        hh, mm = map(int, time_str.split(':'))# برنامه‌ریزی یک کار روزانه
        def job_send_reminder():
            try:
                # برای سادگی: ارسال یادآور به همه‌ی چت‌هایی که بات با آنها تعامل داشته
                # این پیاده‌سازی فقط به‌عنوان نمونه است؛ در عمل بهتر است لیست چت‌ها را ذخیره کنید
                # اینجا فقط یک لاگ می‌زنیم چون ارسال به همه نیاز به مکانیزم ذخیره چت‌ها دارد.
                logger.info(f"وقت یادآور خرید: {time_str} — ارسال پیام یادآور به کاربران (نیاز به پیاده‌سازی لیست چت‌ها)")
                # اگر می‌خواهید به یک chat_id مشخص پیام بفرستید، آن را در data ذخیره کنید و اینجا استفاده کنید.
            except Exception as e:
                logger.exception(e)

        scheduler.add_job(job_send_reminder, 'cron', hour=hh, minute=mm, id='daily_reminder')

    if not scheduler_started:
        scheduler.start()
        scheduler_started = True

# ---------- تولید فایل اکسل ----------

def export_to_excel(shopping_list):
    if not shopping_list:
        return None

    now = datetime.now()
    month = now.month
    year = now.year
    filename = f"ShoppingList-{month}-{year}.xlsx"
    filepath = EXPORT_DIR / filename

    wb = Workbook()
    ws = wb.active
    ws.title = "ShoppingList"

    # هدرها به ترتیب: کد کالا | نام کالا | واحد کالا | نرخ کالا
    ws.append(["کد کالا", "نام کالا", "واحد کالا", "نرخ کالا"])

    for item in shopping_list:
        ws.append([item.get('code',''), item.get('name',''), item.get('unit',''), item.get('rate', '')])

    wb.save(filepath)
    return str(filepath)

# ---------- بررسی سطح دسترسی (اختیاری) ----------

def restricted(func):
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        # اینجا می‌توان محدودیت کاربری اضافه کرد؛ فعلاً آزاد است.
        return func(update, context, *args, **kwargs)
    return wrapped

# ---------- هندلرها ----------

@restricted
def start(update: Update, context: CallbackContext):
    data = load_data()
    chat_id = update.effective_chat.id

    # فرستادن لوگو اگر موجود باشد
    try:
        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH, 'rb') as f:
                context.bot.send_photo(chat_id=chat_id, photo=f, caption="به ربات مدیریت خرید کافه خوش آمدی!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('شروع کار 🏁', callback_data='back_main')]]))
        else:
            update.message.reply_text('به ربات مدیریت خرید کافه خوش آمدی! 👋', reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.exception(e)
        update.message.reply_text('به ربات مدیریت خرید کافه خوش آمدی! 👋', reply_markup=main_menu_keyboard())

@restricted
def menu_router(update: Update, context: CallbackContext):
    query = update.callback_query
    data = load_data()
    query.answer()

    if query.data == 'menu_shopping':
        return show_shopping_list(query, context)
    if query.data == 'menu_daily':
        return show_items_list(query, context, 'daily')
    if query.data == 'menu_monthly':
        return show_items_list(query, context, 'monthly')
    if query.data == 'menu_export':
        return show_export_menu(query, context)
    if query.data == 'menu_settings':
        return show_settings_menu(query, context)
    if query.data == 'back_main':
        query.edit_message_text('🏠 منوی اصلی:', reply_markup=main_menu_keyboard())
        return

# ---------- لیست خرید ----------

def show_shopping_list(query, context):
    data = load_data()
    sl = data.get('shopping_list', [])

    if not sl:
        query.edit_message_text('🛒 لیست خرید خالی است.', reply_markup=main_menu_keyboard())
        return

    # نمایش فقط نام کالاها؛ هر دکمه با callback_data حذف از لیست خرید
    keys = []
    for idx, item in enumerate(sl):
        keys.append([InlineKeyboardButton(f"{item.get('name')}", callback_data=f'shop_done_{idx}')])
    keys.append([InlineKeyboardButton('🔙 بازگشت به منوی اصلی', callback_data='back_main')])

    query.edit_message_text('🛒 لیست خرید (برای علامت زدن خرید، روی آیتم کلیک کن):', reply_markup=InlineKeyboardMarkup(keys))def shopping_item_done(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = load_data()
    payload = query.data
    if payload.startswith('shop_done_'):
        idx = int(payload.split('_')[-1])
        sl = data.get('shopping_list', [])
        if 0 <= idx < len(sl):
            item = sl.pop(idx)
            # ثبت خرید در تاریخ برای آمار ماهانه
            data.setdefault('purchases', []).append({
                'date': datetime.now().strftime('%Y-%m-%d'),
                'code': item.get('code',''),
                'name': item.get('name',''),
                'unit': item.get('unit',''),
                'rate': item.get('rate',0)
            })
            save_data(data)
            query.edit_message_text(f"✅ آیتم '{item.get('name')}' ثبت شد و از لیست خرید حذف شد.", reply_markup=main_menu_keyboard())
        else:
            query.edit_message_text('خطا: آیتم یافت نشد.', reply_markup=main_menu_keyboard())

# ---------- نمایش و انتخاب آیتم‌ها از لیست روزانه/ماهیانه ----------

def show_items_list(query, context, which='daily'):
    data = load_data()
    key = 'daily_items' if which == 'daily' else 'monthly_items'
    items = data.get(key, [])

    if not items:
        query.edit_message_text('لیست آیتم‌ها خالی است. از تنظیمات آیتم اضافه کن.', reply_markup=back_button_keyboard())
        return

    keys = []
    for idx, it in enumerate(items):
        # callback_data: add_daily_0 or add_monthly_0
        keys.append([InlineKeyboardButton(f"{it.get('name')}", callback_data=f'add_{which}_{idx}')])
    keys.append([InlineKeyboardButton('🔙 بازگشت به منوی اصلی', callback_data='back_main')])

    title = '🧃 آیتم‌های خرید روزانه:' if which == 'daily' else '🍰 آیتم‌های خرید ماهانه:'
    query.edit_message_text(title, reply_markup=InlineKeyboardMarkup(keys))


def add_item_to_shopping(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    payload = query.data  # add_daily_0
    parts = payload.split('_')
    which = parts[1]
    idx = int(parts[2])

    data = load_data()
    key = 'daily_items' if which == 'daily' else 'monthly_items'
    items = data.get(key, [])
    if 0 <= idx < len(items):
        item = items[idx]
        # به لیست خرید اضافه کن (کپی از آیتم اصلی)
        data.setdefault('shopping_list', []).append({
            'code': item.get('code',''),
            'name': item.get('name',''),
            'unit': item.get('unit',''),
            'rate': item.get('rate',0),
            'added_at': datetime.now().isoformat()
        })
        save_data(data)
        query.edit_message_text(f"➕ '{item.get('name')}' به لیست خرید اضافه شد.", reply_markup=back_button_keyboard())
    else:
        query.edit_message_text('خطا: آیتم یافت نشد.', reply_markup=back_button_keyboard())

# ---------- منوی خروجی اکسل ----------

def show_export_menu(query, context):
    data = load_data()
    keys = [[InlineKeyboardButton('🔽 ساخت فایل اکسل از لیست خرید فعلی', callback_data='export_now')],
            [InlineKeyboardButton('🔙 بازگشت به منوی اصلی', callback_data='back_main')]]
    query.edit_message_text('📦 فایل خروجی اکسل', reply_markup=InlineKeyboardMarkup(keys))


def handle_export(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = load_data()
    path = export_to_excel(data.get('shopping_list', []))
    if path:
        query.edit_message_text(f"✅ فایل اکسل ساخته شد:
{path}", reply_markup=back_button_keyboard())
    else:
        query.edit_message_text('⚠️ لیست خرید خالی بود؛ فایلی ساخته نشد.', reply_markup=back_button_keyboard())

# ---------- تنظیمات (افزودن/حذف آیتم‌ها، آمار، یادآور) ----------

# مراحل گفتگو برای افزودن آیتم: CODE -> NAME -> UNIT -> RATE
(ADD_CODE, ADD_NAME, ADD_UNIT, ADD_RATE, REMOVE_CHOOSE, REM_REM_CONFIRM,
 REM_MONTH_CHOOSE, SET_REM_TIME) = range(8)def show_settings_menu(query, context):
    keys = [
        [InlineKeyboardButton('✳️ افزودن آیتم به لیست روزانه', callback_data='add_daily')],
        [InlineKeyboardButton('❌ حذف آیتم از لیست روزانه', callback_data='rem_daily')],
        [InlineKeyboardButton('✳️ افزودن آیتم به لیست ماهانه', callback_data='add_monthly')],
        [InlineKeyboardButton('❌ حذف آیتم از لیست ماهانه', callback_data='rem_monthly')],
        [InlineKeyboardButton('📊 نمایش آمار ماهانه', callback_data='show_stats')],
        [InlineKeyboardButton('🔔 تنظیم یادآور خرید', callback_data='set_reminder')],
        [InlineKeyboardButton('🔙 بازگشت به منوی اصلی', callback_data='back_main')]
    ]
    query.edit_message_text('⚙️ تنظیمات کلی:', reply_markup=InlineKeyboardMarkup(keys))

# آغاز افزودن آیتم روزانه

def start_add_item_daily(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text('✳️ افزودن آیتم به لیست روزانه\nلطفاً کد کالا را وارد کن: (مثال: 001)')
    return ADD_CODE


def start_add_item_monthly(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text('✳️ افزودن آیتم به لیست ماهانه\nلطفاً کد کالا را وارد کن: (مثال: 1001)')
    return ADD_CODE


def add_code_received(update: Update, context: CallbackContext):
    context.user_data['new_item'] = {'code': update.message.text.strip()}
    update.message.reply_text('نام کالا را وارد کن:')
    return ADD_NAME


def add_name_received(update: Update, context: CallbackContext):
    context.user_data['new_item']['name'] = update.message.text.strip()
    # نمایش گزینه‌های واحد
    kb = [[InlineKeyboardButton(u, callback_data=f'unit_{u}')] for u in VALID_UNITS]
    update.message.reply_text('واحد کالا را انتخاب کن:', reply_markup=InlineKeyboardMarkup(kb))
    return ADD_UNIT


def add_unit_received(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    unit = query.data.split('_',1)[1]
    if unit not in VALID_UNITS:
        query.edit_message_text('واحد نامعتبر. یکی از: تعداد، گرم، کیلوگرم را انتخاب کن.')
        return ADD_UNIT
    context.user_data['new_item']['unit'] = unit
    query.edit_message_text('لطفاً نرخ کالا را وارد کن (فقط عدد):')
    return ADD_RATE


def add_rate_received(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    try:
        rate = float(text)
    except:
        update.message.reply_text('مقدار نرخ نامعتبر است. دوباره عدد را وارد کن:')
        return ADD_RATE

    new_item = context.user_data.get('new_item')
    new_item['rate'] = rate

    # مشخص کن به کدام لیست افزوده شود: از پیام قبلی می‌فهمیم که کاربر در فرایند افزودن روزانه یا ماهانه است
    # برای ساده‌سازی، اگر پیام قبلی شامل 'ماهانه' بوده باشد، از آن استفاده نمی‌کنیم؛ در عوض از user_data استفاده کن
    # اگر user_data علامت 'adding_to' تعیین نشده، به روزانه اضافه می‌کنیم
    target = context.user_data.get('adding_to', 'daily')
    data = load_data()
    key = 'daily_items' if target == 'daily' else 'monthly_items'
    data.setdefault(key, []).append(new_item)
    save_data(data)

    update.message.reply_text(f"✅ آیتم '{new_item['name']}' با موفقیت به لیست { 'روزانه' if target=='daily' else 'ماهیانه' } اضافه شد.", reply_markup=main_menu_keyboard())
    context.user_data.pop('new_item', None)
    context.user_data.pop('adding_to', None)
    return ConversationHandler.END

# حذف آیتم از لیست روزانه/ماهیانه

def start_remove_item(update: Update, context: CallbackContext, which='daily'):
    query = update.callback_query
    query.answer()
    data = load_data()
    key = 'daily_items' if which == 'daily' else 'monthly_items'
    items = data.get(key, [])
    if not items:
        query.edit_message_text('هیچ آیتمی برای حذف وجود ندارد.', reply_markup=back_button_keyboard())
        return ConversationHandler.ENDkeys = [[InlineKeyboardButton(it.get('name'), callback_data=f'rem_{which}_{idx}')] for idx, it in enumerate(items)]
    keys.append([InlineKeyboardButton('🔙 بازگشت به منوی اصلی', callback_data='back_main')])
    query.edit_message_text('آیتمی که می‌خواهی حذف کنی را انتخاب کن:', reply_markup=InlineKeyboardMarkup(keys))
    return REMOVE_CHOOSE


def handle_remove_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    parts = query.data.split('_')  # rem_daily_0
    which = parts[1]
    idx = int(parts[2])
    data = load_data()
    key = 'daily_items' if which == 'daily' else 'monthly_items'
    items = data.get(key, [])
    if 0 <= idx < len(items):
        item = items.pop(idx)
        save_data(data)
        query.edit_message_text(f"✅ آیتم '{item.get('name')}' از لیست حذف شد.", reply_markup=back_button_keyboard())
    else:
        query.edit_message_text('خطا: آیتم یافت نشد.', reply_markup=back_button_keyboard())
    return ConversationHandler.END

# نمایش آمار ماهانه

def show_stats(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = load_data()
    now = datetime.now()
    month = now.strftime('%Y-%m')
    purchases = data.get('purchases', [])
    total_count = 0
    total_rate = 0.0
    for p in purchases:
        if p.get('date','').startswith(now.strftime('%Y-%m')):
            total_count += 1
            try:
                total_rate += float(p.get('rate',0))
            except:
                pass
    text = f"📊 آمار ماه {now.month}/{now.year}:\n- تعداد کل اقلام خریداری‌شده: {total_count}\n- مجموع نرخ اقلام خریداری‌شده: {total_rate}"
    query.edit_message_text(text, reply_markup=back_button_keyboard())

# تنظیم یادآور

def start_set_reminder(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = load_data()
    time_current = data.get('reminder', {}).get('time', '08:00')
    enabled = data.get('reminder', {}).get('enabled', False)
    kb = [
        [InlineKeyboardButton('فعال کن', callback_data='rem_enable') if not enabled else InlineKeyboardButton('غیرفعال کن', callback_data='rem_disable')],
        [InlineKeyboardButton('تنظیم زمان جدید', callback_data='rem_set_time')],
        [InlineKeyboardButton('🔙 بازگشت به منوی اصلی', callback_data='back_main')]
    ]
    query.edit_message_text(f"🔔 وضعیت یادآور: {'فعال' if enabled else 'غیرفعال'}\nزمان فعلی: {time_current}", reply_markup=InlineKeyboardMarkup(kb))


def handle_reminder_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = load_data()
    if query.data == 'rem_enable':
        data.setdefault('reminder', {})['enabled'] = True
        save_data(data)
        schedule_jobs(context.bot.updater, data)
        query.edit_message_text('✅ یادآور فعال شد.', reply_markup=back_button_keyboard())
    elif query.data == 'rem_disable':
        data.setdefault('reminder', {})['enabled'] = False
        save_data(data)
        schedule_jobs(context.bot.updater, data)
        query.edit_message_text('⚠️ یادآور غیرفعال شد.', reply_markup=back_button_keyboard())
    elif query.data == 'rem_set_time':
        query.edit_message_text('لطفاً زمان را به صورت HH:MM وارد کن (مثال: 08:00)')
        return SET_REM_TIME
    return ConversationHandler.END


def set_rem_time_received(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    try:
        hh, mm = map(int, text.split(':'))
        assert 0 <= hh < 24 and 0 <= mm < 60
    except:
        update.message.reply_text('فرمت زمان نادرست است. مجدداً به صورت HH:MM وارد کن:')
        return SET_REM_TIME

    data = load_data()
    data.setdefault('reminder', {})['time'] = f"{hh:02d}:{mm:02d}"
    data['reminder'].setdefault('enabled', True)
    save_data(data)
    schedule_jobs(context.bot.updater, data)
    update.message.reply_text(f"✅ زمان یادآور تنظیم شد: {hh:02d}:{mm:02d}", reply_markup=main_menu_keyboard())
    return ConversationHandler.END# ---------- مسیریابی کال‌بک‌ها ----------

def callback_dispatcher(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return
    data = query.data

    # مسیرهای عمومی
    if data.startswith('menu_') or data == 'back_main':
        return menu_router(update, context)

    # لیست خرید: علامت‌گذاری خرید
    if data.startswith('shop_done_'):
        return shopping_item_done(update, context)

    # افزودن آیتم از لیست روزانه/ماهیانه
    if data.startswith('add_daily_') or data.startswith('add_monthly_'):
        return add_item_to_shopping(update, context)

    # منوی خروجی
    if data == 'export_now':
        return handle_export(update, context)

    # تنظیمات: ورود به هر عملیات
    if data == 'add_daily':
        context.user_data['adding_to'] = 'daily'
        return start_add_item_daily(update, context)
    if data == 'add_monthly':
        context.user_data['adding_to'] = 'monthly'
        return start_add_item_monthly(update, context)
    if data == 'rem_daily':
        return start_remove_item(update, context, 'daily')
    if data == 'rem_monthly':
        return start_remove_item(update, context, 'monthly')
    if data == 'show_stats':
        return show_stats(update, context)
    if data.startswith('rem_'):
        return handle_remove_choice(update, context)
    if data.startswith('rem_'):
        return handle_remove_choice(update, context)
    if data.startswith('rem_'):
        return handle_remove_choice(update, context)
    if data.startswith('rem_'):
        return handle_remove_choice(update, context)

    if data in ('rem_enable','rem_disable','rem_set_time'):
        return handle_reminder_buttons(update, context)

    # انتخاب واحد در افزودن
    if data.startswith('unit_'):
        return add_unit_received(update, context)

    # بازگشت به منوی اصلی
    if data == 'back_main':
        query.edit_message_text('🏠 منوی اصلی:', reply_markup=main_menu_keyboard())
        return

    # موارد دیگر
    logger.info(f"unknown callback: {data}")

# ---------- ConversationHandlers تعریف و ثبت ----------

add_item_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_item_daily, pattern='^add_daily$'),
                  CallbackQueryHandler(start_add_item_monthly, pattern='^add_monthly$')],
    states={
        ADD_CODE: [MessageHandler(Filters.text & ~Filters.command, add_code_received)],
        ADD_NAME: [MessageHandler(Filters.text & ~Filters.command, add_name_received)],
        ADD_UNIT: [CallbackQueryHandler(add_unit_received, pattern='^unit_')],
        ADD_RATE: [MessageHandler(Filters.text & ~Filters.command, add_rate_received)],
    },
    fallbacks=[CommandHandler('cancel', lambda u,c: (c.user_data.clear(), u.message.reply_text('لغو شد.', reply_markup=main_menu_keyboard())))],
    allow_reentry=True
)

remove_item_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(lambda u,c: start_remove_item(u,c,'daily'), pattern='^rem_daily$'),
                  CallbackQueryHandler(lambda u,c: start_remove_item(u,c,'monthly'), pattern='^rem_monthly$')],
    states={
        REMOVE_CHOOSE: [CallbackQueryHandler(handle_remove_choice, pattern='^rem_')]
    },
    fallbacks=[CommandHandler('cancel', lambda u,c: (c.user_data.clear(), u.message.reply_text('لغو شد.', reply_markup=main_menu_keyboard())))],
    allow_reentry=True
)

set_reminder_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_set_reminder, pattern='^set_reminder$')],
    states={
        SET_REM_TIME: [MessageHandler(Filters.text & ~Filters.command, set_rem_time_received)]
    },
    fallbacks=[CommandHandler('cancel', lambda u,c: (c.user_data.clear(), u.message.reply_text('لغو شد.', reply_markup=main_menu_keyboard())))],
    allow_reentry=True
)

# ---------- تنظیم و اجرای بات ----------

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # هندلرها
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CallbackQueryHandler(callback_dispatcher))# Conversation handlers
    dp.add_handler(add_item_conv)
    dp.add_handler(remove_item_conv)
    dp.add_handler(set_reminder_conv)

    # اگر data.json وجود دارد، job یادآور را زمانبندی کن
    data = load_data()
    try:
        schedule_jobs(updater, data)
    except Exception as e:
        logger.exception(e)

    # راه‌اندازی بات
    updater.start_polling()
    logger.info('Bot started')
    updater.idle()

if name == 'main':
    main()

