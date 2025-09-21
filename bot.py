import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import random

# تنظیم لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# توکن ربات خودتان را اینجا وارد کنید
BOT_TOKEN = "7685135237:AAEmsHktRw9cEqrHTkCoPZk-fBimK7TDjOo"

# دیتابیس ساده برای ذخیره امتیاز بازیکنان
user_scores = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ربات"""
    user = update.effective_user
    user_id = user.id
    
    # اضافه کردن کاربر به دیتابیس اگر وجود نداشته باشد
    if user_id not in user_scores:
        user_scores[user_id] = {"wins": 0, "losses": 0}
    
    welcome_message = f"""
سلام {user.first_name}! 👋

به بازی شیر یا خط خوش آمدی! 🪙

🎮 نحوه بازی:
- یکی از دکمه‌های شیر یا خط را انتخاب کن
- من سکه رو پرتاب می‌کنم
- اگر انتخابت درست باشد برنده می‌شوی! 🏆

📊 امتیاز فعلی شما:
برد: {user_scores[user_id]['wins']}
باخت: {user_scores[user_id]['losses']}

برای شروع بازی دستور /play را بزن!
    """
    
    await update.message.reply_text(welcome_message)

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع یک بازی جدید"""
    keyboard = [
        [
            InlineKeyboardButton("🦁 شیر", callback_data='heads'),
            InlineKeyboardButton("➖ خط", callback_data='tails')
        ],
        [
            InlineKeyboardButton("📊 مشاهده امتیاز", callback_data='score')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🪙 سکه آماده پرتاب است!\n\nانتخاب خودت رو بکن:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش کلیک روی دکمه‌ها"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # اضافه کردن کاربر به دیتابیس اگر وجود نداشته باشد
    if user_id not in user_scores:
        user_scores[user_id] = {"wins": 0, "losses": 0}
    
    if query.data == 'score':
        # نمایش امتیاز
        score_message = f"""
📊 امتیاز شما:

🏆 برد: {user_scores[user_id]['wins']}
😔 باخت: {user_scores[user_id]['losses']}

کل بازی‌ها: {user_scores[user_id]['wins'] + user_scores[user_id]['losses']}
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🦁 شیر", callback_data='heads'),
                InlineKeyboardButton("➖ خط", callback_data='tails')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            score_message + "\n\nبرای بازی جدید یکی از دکمه‌ها را انتخاب کن:",
            reply_markup=reply_markup
        )
        
    elif query.data in ['heads', 'tails']:
        # شروع بازی
        user_choice = "شیر" if query.data == 'heads' else "خط"
        
        # پرتاب سکه
        coin_result = random.choice(['heads', 'tails'])
        coin_result_persian = "شیر" if coin_result == 'heads' else "خط"
        
        # بررسی برنده
        if query.data == coin_result:
            # برنده!
            user_scores[user_id]['wins'] += 1
            result_message = f"""
🪙 در حال پرتاب سکه...

انتخاب شما: {user_choice}
نتیجه: {coin_result_persian}

🎉 تبریک! شما برنده شدید! 🏆

📊 امتیاز جدید:
برد: {user_scores[user_id]['wins']}
باخت: {user_scores[user_id]['losses']}
            """
        else:
            # باخت
            user_scores[user_id]['losses'] += 1
            result_message = f"""
🪙 در حال پرتاب سکه...

انتخاب شما: {user_choice}
نتیجه: {coin_result_persian}

😔 متأسفانه باختید!

📊 امتیاز جدید:
برد: {user_scores[user_id]['wins']}
باخت: {user_scores[user_id]['losses']}
            """
        
        # دکمه‌های بازی جدید
        keyboard = [
            [
                InlineKeyboardButton("🔄 بازی جدید", callback_data='new_game'),
                InlineKeyboardButton("📊 مشاهده امتیاز", callback_data='score')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            result_message,
            reply_markup=reply_markup
        )
        
    elif query.data == 'new_game':
        # بازی جدید
        keyboard = [
            [
                InlineKeyboardButton("🦁 شیر", callback_data='heads'),
                InlineKeyboardButton("➖ خط", callback_data='tails')
            ],
            [
                InlineKeyboardButton("📊 مشاهده امتیاز", callback_data='score')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🪙 سکه آماده پرتاب است!\n\nانتخاب خودت رو بکن:",
            reply_markup=reply_markup
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنمای ربات"""
    help_text = """
🎮 راهنمای بازی شیر یا خط:

📋 دستورات:
/start - شروع ربات
/play - شروع بازی جدید  
/help - نمایش این راهنما
/score - مشاهده امتیاز

🎯 نحوه بازی:
1. دستور /play را بزن
2. یکی از دکمه‌های شیر یا خط را انتخاب کن
3. منتظر نتیجه پرتاب سکه باش
4. اگر حدست درست باشد برنده می‌شوی!

🏆 امتیازگذاری:
- هر برد: +1 امتیاز
- هر باخت: +1 به شمارنده باخت
- امتیازها ذخیره می‌شوند

موفق باشی! 🍀
    """
    await update.message.reply_text(help_text)

async def score_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش امتیاز کاربر"""
    user_id = update.effective_user.id
    
    if user_id not in user_scores:
        user_scores[user_id] = {"wins": 0, "losses": 0}
    
    score_message = f"""
📊 امتیاز شما:

🏆 برد: {user_scores[user_id]['wins']}
😔 باخت: {user_scores[user_id]['losses']}

کل بازی‌ها: {user_scores[user_id]['wins'] + user_scores[user_id]['losses']}

برای بازی دستور /play را بزن!
    """
    
    await update.message.reply_text(score_message)

def main():
    """راه‌اندازی ربات"""
    # ساخت اپلیکیشن
    application = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("score", score_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # شروع ربات
    print("ربات شیر یا خط شروع شد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
