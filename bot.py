import os
import json
import random
import time
import asyncio
import requests
import hashlib
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import sqlite3
from threading import Timer
import uuid

# تنظیمات ربات
BOT_TOKEN = "7685135237:AAEmsHktRw9cEqrHTkCoPZk-fBimK7TDjOo"
ADMIN_ID = "327855654"  # آیدی ادمین
GROUP_ID = "https://t.me/tolidmortza"  # آیدی گروه
PAYPING_API_KEY = "D17C0938BD1340A1C2C9D45ED65B14EA69A4CD122E8265D264830B952FEBE07F-1"
PAYPING_API_URL = "https://api.payping.ir/v2/pay"

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect('game_bot.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # جدول کاربران
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول بازی‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                question1 TEXT,
                answer1 INTEGER,
                options1 TEXT,
                question2 TEXT,
                answer2 INTEGER,
                options2 TEXT,
                total_players INTEGER DEFAULT 0,
                prize_pool INTEGER DEFAULT 0,
                status TEXT DEFAULT 'waiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول شرکت‌کنندگان
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                game_id TEXT,
                answer1 INTEGER,
                answer2 INTEGER,
                answer1_time INTEGER,
                answer2_time INTEGER,
                bet_amount INTEGER DEFAULT 100,
                final_amount INTEGER DEFAULT 0,
                is_winner BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (game_id) REFERENCES games (game_id)
            )
        ''')
        
        # جدول برداشت‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                card_number TEXT,
                full_name TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # جدول پرداخت‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                payment_code TEXT UNIQUE,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, referred_by=None):
        cursor = self.conn.cursor()
        referral_code = f"REF_{user_id}_{random.randint(1000, 9999)}"
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, referral_code, referred_by)
                VALUES (?, ?, ?)
            ''', (user_id, referral_code, referred_by))
            self.conn.commit()
            return referral_code
        except:
            return None
    
    def get_user_balance(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    
    def update_balance(self, user_id, amount):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET balance = balance + ? WHERE user_id = ?
        ''', (amount, user_id))
        self.conn.commit()
    
    def create_game(self, game_id, question1, answer1, options1, question2, answer2, options2):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO games (game_id, question1, answer1, options1, question2, answer2, options2)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (game_id, question1, answer1, json.dumps(options1), question2, answer2, json.dumps(options2)))
        self.conn.commit()
    
    def add_participant(self, user_id, game_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO participants (user_id, game_id)
            VALUES (?, ?)
        ''', (user_id, game_id))
        self.conn.commit()
    
    def get_game_info(self, game_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM games WHERE game_id = ?', (game_id,))
        return cursor.fetchone()
    
    def update_participant_answer(self, user_id, game_id, question_num, answer, response_time):
        cursor = self.conn.cursor()
        if question_num == 1:
            cursor.execute('''
                UPDATE participants SET answer1 = ?, answer1_time = ?
                WHERE user_id = ? AND game_id = ?
            ''', (answer, response_time, user_id, game_id))
        else:
            cursor.execute('''
                UPDATE participants SET answer2 = ?, answer2_time = ?
                WHERE user_id = ? AND game_id = ?
            ''', (answer, response_time, user_id, game_id))
        self.conn.commit()
    
    def get_participants(self, game_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM participants WHERE game_id = ?', (game_id,))
        return cursor.fetchall()
    
    def add_withdrawal_request(self, user_id, amount, card_number, full_name):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO withdrawals (user_id, amount, card_number, full_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, amount, card_number, full_name))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_pending_withdrawals(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT w.*, u.user_id FROM withdrawals w
            JOIN users u ON w.user_id = u.user_id
            WHERE w.status = 'pending'
        ''')
        return cursor.fetchall()

class MathGameBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.current_game = None
        self.question_start_time = None
        self.game_participants = {}
        self.used_questions = set()
        
    def generate_math_question(self):
        """تولید سوال ریاضی تصادفی"""
        while True:
            # تولید اعداد تصادفی
            nums = [random.randint(10, 100) for _ in range(6)]
            operators = ['+', '-', '×', '÷']
            
            # ساخت سوال
            question = f"{nums[0]}×{nums[1]}÷{nums[2]}×{nums[3]}+{nums[4]}-{nums[5]}×2="
            
            # محاسبه جواب صحیح
            try:
                # تبدیل × به * و ÷ به /
                calc_question = question.replace('×', '*').replace('÷', '/').replace('=', '')
                correct_answer = int(eval(calc_question))
                
                if question not in self.used_questions:
                    self.used_questions.add(question)
                    
                    # تولید گزینه‌های اشتباه
                    wrong_answers = []
                    for _ in range(3):
                        wrong = correct_answer + random.randint(-50, 50)
                        if wrong != correct_answer and wrong not in wrong_answers:
                            wrong_answers.append(wrong)
                    
                    # اگر سه جواب اشتباه نداشتیم، تولید کن
                    while len(wrong_answers) < 3:
                        wrong = correct_answer + random.randint(-100, 100)
                        if wrong != correct_answer and wrong not in wrong_answers:
                            wrong_answers.append(wrong)
                    
                    # ترکیب گزینه‌ها
                    options = [correct_answer] + wrong_answers[:3]
                    random.shuffle(options)
                    
                    return question, correct_answer, options
            except:
                continue
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور شروع"""
        user_id = update.effective_user.id
        
        # بررسی رفرال
        referred_by = None
        if context.args:
            ref_code = context.args[0]
            cursor = self.db.conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref_code,))
            result = cursor.fetchone()
            if result:
                referred_by = result[0]
        
        # اضافه کردن کاربر
        referral_code = self.db.add_user(user_id, referred_by)
        
        # پاداش رفرال
        if referred_by:
            self.db.update_balance(referred_by, 50)  # 50 تومان پاداش رفرال
        
        # دکمه‌های اصلی
        keyboard = [
            [InlineKeyboardButton("💰 پرداخت", callback_data="payment"),
             InlineKeyboardButton("🎮 بازی کردن", callback_data="play_game")],
            [InlineKeyboardButton("👥 رفرال", callback_data="referral"),
             InlineKeyboardButton("💸 برداشت", callback_data="withdraw")]
        ]
        
        if str(user_id) == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🔧 پنل ادمین", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        balance = self.db.get_user_balance(user_id)
        
        await update.message.reply_text(
            f"🎯 به ربات بازی ریاضی خوش آمدید!\n\n"
            f"💰 موجودی شما: {balance:,} تومان\n"
            f"🔗 کد رفرال شما: `{referral_code}`\n\n"
            f"برای شروع بازی، ابتدا موجودی خود را شارژ کنید.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت دکمه‌ها"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data == "payment":
            await self.handle_payment(query, context)
        elif data == "play_game":
            await self.handle_play_game(query, context)
        elif data == "referral":
            await self.handle_referral(query, context)
        elif data == "withdraw":
            await self.handle_withdraw(query, context)
        elif data == "admin_panel" and str(user_id) == ADMIN_ID:
            await self.handle_admin_panel(query, context)
        elif data.startswith("answer_"):
            await self.handle_answer(query, context)
        elif data == "register_game":
            await self.register_for_game(query, context)
        elif data.startswith("approve_withdrawal_"):
            await self.approve_withdrawal(query, context)
    
    async def handle_payment(self, query, context):
        """مدیریت پرداخت"""
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ایجاد درخواست پرداخت PayPing
        payment_code = str(uuid.uuid4())
        
        headers = {
            'Authorization': f'Bearer {PAYPING_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'amount': 100,  # 100 تومان
            'payerIdentity': str(query.from_user.id),
            'payerName': query.from_user.first_name,
            'description': 'شارژ موجودی بازی ریاضی',
            'returnUrl': f'https://t.me/Maynir_Bot',
            'clientRefId': payment_code
        }
        
        try:
            response = requests.post(PAYPING_API_URL, json=data, headers=headers)
            if response.status_code == 200:
                result = response.json()
                payment_url = result['code']
                
                # ذخیره در دیتابیس
                cursor = self.db.conn.cursor()
                cursor.execute('''
                    INSERT INTO payments (user_id, amount, payment_code)
                    VALUES (?, ?, ?)
                ''', (query.from_user.id, 100, payment_code))
                self.db.conn.commit()
                
                keyboard = [
                    [InlineKeyboardButton("💳 پرداخت 100 تومان", url=f"https://api.payping.ir/v2/pay/gotoipg/{payment_url}")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    "💳 برای پرداخت بر روی دکمه زیر کلیک کنید:\n\n"
                    "✅ پس از پرداخت موفق، موجودی شما بلافاصله شارژ خواهد شد.",
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    "❌ خطا در ایجاد درگاه پرداخت. لطفاً مجدداً تلاش کنید.",
                    reply_markup=reply_markup
                )
        except Exception as e:
            await query.edit_message_text(
                "❌ خطا در اتصال به درگاه پرداخت. لطفاً مجدداً تلاش کنید.",
                reply_markup=reply_markup
            )
    
    async def handle_play_game(self, query, context):
        """مدیریت بازی"""
        user_id = query.from_user.id
        balance = self.db.get_user_balance(user_id)
        
        if balance < 100:
            keyboard = [
                [InlineKeyboardButton("💰 شارژ حساب", callback_data="payment")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "❌ موجودی شما کافی نیست!\n\n"
                "💰 حداقل موجودی مورد نیاز: 100 تومان\n"
                f"💳 موجودی فعلی شما: {balance:,} تومان",
                reply_markup=reply_markup
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ ثبت نام در بازی (100 تومان)", callback_data="register_game")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎮 آیا مایل به شرکت در بازی هستید؟\n\n"
            "💰 هزینه شرکت: 100 تومان\n"
            "⏰ بازی هر روز ساعت 22:00 شروع می‌شود\n"
            "🏆 برندگان تمام جایزه را تقسیم می‌کنند\n\n"
            "⚠️ برای برنده شدن باید هر دو سوال را درست پاسخ دهید!",
            reply_markup=reply_markup
        )
    
    async def register_for_game(self, query, context):
        """ثبت نام در بازی"""
        user_id = query.from_user.id
        
        # کسر موجودی
        self.db.update_balance(user_id, -100)
        
        # اگر بازی‌ای در حال اجرا نیست، ایجاد کن
        if not self.current_game:
            self.current_game = f"game_{int(time.time())}"
            question1, answer1, options1 = self.generate_math_question()
            question2, answer2, options2 = self.generate_math_question()
            
            self.db.create_game(self.current_game, question1, answer1, options1, question2, answer2, options2)
        
        # ثبت شرکت‌کننده
        self.db.add_participant(user_id, self.current_game)
        
        await query.edit_message_text(
            "✅ شما با موفقیت در بازی ثبت نام شدید!\n\n"
            "⏰ بازی تا 15 دقیقه دیگر شروع خواهد شد.\n"
            "📢 سوالات در گروه ارسال خواهد شد."
        )
        
        # شروع تایمر 15 دقیقه‌ای
        Timer(900, lambda: asyncio.create_task(self.start_game(context))).start()
    
    async def start_game(self, context):
        """شروع بازی در گروه"""
        if not self.current_game:
            return
        
        game_info = self.db.get_game_info(self.current_game)
        if not game_info:
            return
        
        question1 = game_info[1]
        options1 = json.loads(game_info[3])
        
        # ساخت کیبورد سوال اول
        keyboard = [
            [InlineKeyboardButton(f"A) {options1[0]}", callback_data=f"answer_1_{options1[0]}"),
             InlineKeyboardButton(f"B) {options1[1]}", callback_data=f"answer_1_{options1[1]}")],
            [InlineKeyboardButton(f"C) {options1[2]}", callback_data=f"answer_1_{options1[2]}"),
             InlineKeyboardButton(f"D) {options1[3]}", callback_data=f"answer_1_{options1[3]}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ارسال سوال در گروه
        self.question_start_time = time.time()
        
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"🎯 سوال اول:\n\n"
                 f"📊 {question1}\n\n"
                 f"⏰ مهلت پاسخگویی: 20 ثانیه",
            reply_markup=reply_markup
        )
        
        # تایمر 20 ثانیه برای سوال اول
        Timer(20, lambda: asyncio.create_task(self.end_question_1(context))).start()
    
    async def handle_answer(self, query, context):
        """مدیریت پاسخ‌ها"""
        user_id = query.from_user.id
        data = query.data
        
        if not self.current_game:
            await query.answer("❌ هیچ بازی فعالی وجود ندارد!")
            return
        
        # استخراج شماره سوال و پاسخ
        parts = data.split("_")
        question_num = int(parts[1])
        answer = int(parts[2])
        
        # محاسبه زمان پاسخ
        response_time = int(time.time() - self.question_start_time)
        
        if response_time > 20:
            await query.answer("⏰ زمان پاسخگویی به پایان رسیده!")
            return
        
        # ثبت پاسخ
        self.db.update_participant_answer(user_id, self.current_game, question_num, answer, response_time)
        
        await query.answer(f"✅ پاسخ شما ثبت شد! (زمان: {response_time} ثانیه)")
    
    async def end_question_1(self, context):
        """پایان سوال اول و شروع سوال دوم"""
        game_info = self.db.get_game_info(self.current_game)
        question2 = game_info[4]
        options2 = json.loads(game_info[6])
        
        # نمایش جواب سوال اول
        correct_answer1 = game_info[2]
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"⏰ زمان سوال اول به پایان رسید!\n\n"
                 f"✅ پاسخ صحیح: {correct_answer1}\n\n"
                 f"🎯 سوال دوم:"
        )
        
        # ساخت کیبورد سوال دوم
        keyboard = [
            [InlineKeyboardButton(f"A) {options2[0]}", callback_data=f"answer_2_{options2[0]}"),
             InlineKeyboardButton(f"B) {options2[1]}", callback_data=f"answer_2_{options2[1]}")],
            [InlineKeyboardButton(f"C) {options2[2]}", callback_data=f"answer_2_{options2[2]}"),
             InlineKeyboardButton(f"D) {options2[3]}", callback_data=f"answer_2_{options2[3]}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        self.question_start_time = time.time()
        
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"📊 {question2}\n\n"
                 f"⏰ مهلت پاسخگویی: 20 ثانیه",
            reply_markup=reply_markup
        )
        
        # تایمر 20 ثانیه برای سوال دوم
        Timer(20, lambda: asyncio.create_task(self.end_game(context))).start()
    
    async def end_game(self, context):
        """پایان بازی و تعیین برندگان"""
        game_info = self.db.get_game_info(self.current_game)
        correct_answer1 = game_info[2]
        correct_answer2 = game_info[5]
        
        # دریافت تمام شرکت‌کنندگان
        participants = self.db.get_participants(self.current_game)
        
        winners = []
        losers = []
        
        for participant in participants:
            user_id = participant[1]
            answer1 = participant[3]
            answer2 = participant[4]
            time1 = participant[5] or 21
            time2 = participant[6] or 21
            
            # محاسبه درصد بر اساس زمان
            if answer1 == correct_answer1 and answer2 == correct_answer2 and time1 <= 20 and time2 <= 20:
                score = (40 - time1 - time2) / 40 * 100  # درصد بر اساس سرعت
                winners.append((user_id, score, time1, time2))
            else:
                # محاسبه میزان پول از دست رفته
                loss_percent = 0
                if time1 <= 20 and answer1 != correct_answer1:
                    loss_percent += time1 / 20 * 50  # 50% برای سوال اول
                if time2 <= 20 and answer2 != correct_answer2:
                    loss_percent += time2 / 20 * 50  # 50% برای سوال دوم
                
                loss_amount = int(100 * loss_percent / 100)
                losers.append((user_id, loss_amount))
        
        # محاسبه جایزه
        total_prize = len(participants) * 100
        
        if winners:
            total_score = sum([w[1] for w in winners])
            
            result_text = f"🎉 بازی به پایان رسید!\n\n"
            result_text += f"✅ پاسخ صحیح سوال دوم: {correct_answer2}\n\n"
            result_text += f"👥 تعداد شرکت‌کنندگان: {len(participants)}\n"
            result_text += f"🏆 تعداد برندگان: {len(winners)}\n"
            result_text += f"💰 کل جایزه: {total_prize:,} تومان\n\n"
            result_text += "🥇 برندگان:\n"
            
            for i, (user_id, score, time1, time2) in enumerate(winners, 1):
                prize = int(total_prize * (score / total_score))
                self.db.update_balance(user_id, prize)
                
                try:
                    user = await context.bot.get_chat(user_id)
                    name = user.first_name
                except:
                    name = f"User {user_id}"
                
                result_text += f"{i}. {name}: {prize:,} تومان\n"
            
        else:
            result_text = f"😔 متأسفانه هیچ برنده‌ای نداشتیم!\n\n"
            result_text += f"👥 تعداد شرکت‌کنندگان: {len(participants)}\n"
            result_text += f"✅ پاسخ صحیح سوال دوم: {correct_answer2}"
        
        await context.bot.send_message(chat_id=GROUP_ID, text=result_text)
        
        # ریست بازی
        self.current_game = None
        
        # پیام برای شروع بازی بعدی
        keyboard = [
            [InlineKeyboardButton("🎮 بازی مجدد", url="https://t.me/Maynir_Bot")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        Timer(5, lambda: asyncio.create_task(
            context.bot.send_message(
                chat_id=GROUP_ID,
                text="🎯 آیا می‌خواهید دوباره بازی کنید؟\n\n"
                     "⏰ بازی بعدی تا 15 دقیقه دیگر شروع می‌شود!",
                reply_markup=reply_markup
            )
        )).start()
    
    async def handle_referral(self, query, context):
        """مدیریت رفرال"""
        user_id = query.from_user.id
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            referral_code = result[0]
            referral_link = f"https://t.me/Maynir_Bot?start={referral_code}"
            
            keyboard = [
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"👥 دعوت دوستان و کسب درآمد!\n\n"
                f"🔗 لینک دعوت شما:\n`{referral_link}`\n\n"
                f"💰 به ازای هر دعوت موفق 50 تومان دریافت کنید!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def handle_withdraw(self, query, context):
        """مدیریت برداشت"""
        user_id = query.from_user.id
        balance = self.db.get_user_balance(user_id)
        
        if balance < 1000:
            keyboard = [
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"❌ موجودی کافی برای برداشت ندارید!\n\n"
                f"💰 موجودی فعلی: {balance:,} تومان\n"
                f"💳 حداقل موجودی برای برداشت: 1,000 تومان\n"
                f"🏦 حداکثر مبلغ برداشت: 1,000,000 تومان",
                reply_markup=reply_markup
            )
            return
        
        # درخواست مبلغ برداشت
        context.user_data['withdraw_step'] = 'amount'
        keyboard = [
            [InlineKeyboardButton("🔙 انصراف", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💸 درخواست برداشت\n\n"
            f"💰 موجودی شما: {balance:,} تومان\n"
            f"🏦 حداکثر برداشت: 1,000,000 تومان\n\n"
            f"لطفاً مبلغ مورد نظر را وارد کنید:",
            reply_markup=reply_markup
        )
    
    async def handle_admin_panel(self, query, context):
        """پنل ادمین"""
        pending_withdrawals = self.db.get_pending_withdrawals()
        
        keyboard = [
            [InlineKeyboardButton(f"💸 درخواست‌های برداشت ({len(pending_withdrawals)})", callback_data="view_withdrawals")],
            [InlineKeyboardButton("📊 آمار کلی", callback_data="general_stats")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔧 پنل مدیریت\n\n"
            "از گزینه‌های زیر انتخاب کنید:",
            reply_markup=reply_markup
        )
    
    async def view_withdrawals(self, query, context):
        """نمایش درخواست‌های برداشت"""
        withdrawals = self.db.get_pending_withdrawals()
        
        if not withdrawals:
            keyboard = [
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "✅ هیچ درخواست برداشت معلقی وجود ندارد!",
                reply_markup=reply_markup
            )
            return
        
        text = "💸 درخواست‌های برداشت:\n\n"
        keyboard = []
        
        for withdrawal in withdrawals[:10]:  # نمایش 10 تای اول
            withdrawal_id = withdrawal[0]
            user_id = withdrawal[1]
            amount = withdrawal[2]
            card_number = withdrawal[3]
            full_name = withdrawal[4]
            
            text += f"🆔 ID: {withdrawal_id}\n"
            text += f"👤 کاربر: {user_id}\n"
            text += f"💰 مبلغ: {amount:,} تومان\n"
            text += f"💳 کارت: {card_number}\n"
            text += f"👨‍💼 نام: {full_name}\n"
            text += "➖➖➖➖➖➖➖➖\n"
            
            keyboard.append([
                InlineKeyboardButton(f"✅ تایید #{withdrawal_id}", callback_data=f"approve_withdrawal_{withdrawal_id}"),
                InlineKeyboardButton(f"❌ رد #{withdrawal_id}", callback_data=f"reject_withdrawal_{withdrawal_id}")
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def approve_withdrawal(self, query, context):
        """تایید برداشت"""
        withdrawal_id = int(query.data.split("_")[2])
        
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT user_id, amount FROM withdrawals WHERE id = ?', (withdrawal_id,))
        result = cursor.fetchone()
        
        if result:
            user_id, amount = result
            
            # تغییر وضعیت برداشت به تایید شده
            cursor.execute('''
                UPDATE withdrawals SET status = 'approved'
                WHERE id = ?
            ''', (withdrawal_id,))
            self.db.conn.commit()
            
            # کسر از موجودی کاربر
            self.db.update_balance(user_id, -amount)
            
            # اطلاع به کاربر
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ درخواست برداشت شما با موفقیت تایید و واریز شد!\n\n"
                         f"💰 مبلغ: {amount:,} تومان"
                )
            except:
                pass
            
            await query.answer("✅ برداشت با موفقیت تایید شد!")
            
            # بازگشت به لیست برداشت‌ها
            await self.view_withdrawals(query, context)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت پیام‌های متنی"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # مدیریت مراحل برداشت
        if 'withdraw_step' in context.user_data:
            step = context.user_data['withdraw_step']
            
            if step == 'amount':
                try:
                    amount = int(text.replace(',', ''))
                    balance = self.db.get_user_balance(user_id)
                    
                    if amount < 1000 or amount > 1000000:
                        await update.message.reply_text(
                            "❌ مبلغ نامعتبر!\n"
                            "حداقل: 1,000 تومان\n"
                            "حداکثر: 1,000,000 تومان"
                        )
                        return
                    
                    if amount > balance:
                        await update.message.reply_text(
                            f"❌ موجودی کافی ندارید!\n"
                            f"موجودی شما: {balance:,} تومان"
                        )
                        return
                    
                    context.user_data['withdraw_amount'] = amount
                    context.user_data['withdraw_step'] = 'card'
                    
                    await update.message.reply_text(
                        f"💳 مبلغ {amount:,} تومان ثبت شد.\n\n"
                        "لطفاً شماره کارت خود را وارد کنید:\n"
                        "(16 رقم بدون فاصله)"
                    )
                    
                except ValueError:
                    await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
            
            elif step == 'card':
                if len(text) != 16 or not text.isdigit():
                    await update.message.reply_text(
                        "❌ شماره کارت نامعتبر!\n"
                        "لطفاً 16 رقم شماره کارت را بدون فاصله وارد کنید."
                    )
                    return
                
                context.user_data['withdraw_card'] = text
                context.user_data['withdraw_step'] = 'name'
                
                await update.message.reply_text(
                    "👤 شماره کارت ثبت شد.\n\n"
                    "لطفاً نام و نام خانوادگی صاحب کارت را وارد کنید:"
                )
            
            elif step == 'name':
                if len(text.strip()) < 3:
                    await update.message.reply_text(
                        "❌ نام وارد شده کوتاه است!\n"
                        "لطفاً نام و نام خانوادگی کامل را وارد کنید."
                    )
                    return
                
                # ثبت درخواست برداشت
                amount = context.user_data['withdraw_amount']
                card = context.user_data['withdraw_card']
                
                withdrawal_id = self.db.add_withdrawal_request(user_id, amount, card, text.strip())
                
                # پاک کردن داده‌های موقت
                del context.user_data['withdraw_step']
                del context.user_data['withdraw_amount']
                del context.user_data['withdraw_card']
                
                await update.message.reply_text(
                    f"✅ درخواست برداشت شما ثبت شد!\n\n"
                    f"🆔 کد پیگیری: #{withdrawal_id}\n"
                    f"💰 مبلغ: {amount:,} تومان\n"
                    f"💳 کارت: {card}\n"
                    f"👤 نام: {text.strip()}\n\n"
                    f"⏰ در بازه زمانی یک هفته (احتمالاً زودتر) واریز خواهد شد."
                )
                
                # اطلاع به ادمین
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"🔔 درخواست برداشت جدید!\n\n"
                             f"🆔 ID: #{withdrawal_id}\n"
                             f"👤 کاربر: {user_id}\n"
                             f"💰 مبلغ: {amount:,} تومان\n"
                             f"💳 کارت: {card}\n"
                             f"👨‍💼 نام: {text.strip()}"
                    )
                except:
                    pass
    
    async def back_to_main(self, query, context):
        """بازگشت به منوی اصلی"""
        user_id = query.from_user.id
        balance = self.db.get_user_balance(user_id)
        
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        referral_code = result[0] if result else "نامشخص"
        
        keyboard = [
            [InlineKeyboardButton("💰 پرداخت", callback_data="payment"),
             InlineKeyboardButton("🎮 بازی کردن", callback_data="play_game")],
            [InlineKeyboardButton("👥 رفرال", callback_data="referral"),
             InlineKeyboardButton("💸 برداشت", callback_data="withdraw")]
        ]
        
        if str(user_id) == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🔧 پنل ادمین", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎯 به ربات بازی ریاضی خوش آمدید!\n\n"
            f"💰 موجودی شما: {balance:,} تومان\n"
            f"🔗 کد رفرال شما: `{referral_code}`\n\n"
            f"برای شروع بازی، ابتدا موجودی خود را شارژ کنید.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# کلاس اصلی برای اجرای ربات
class TelegramBot:
    def __init__(self):
        self.game_bot = MathGameBot()
        
    def run(self):
        """اجرای ربات"""
        app = Application.builder().token(BOT_TOKEN).build()
        
        # اضافه کردن هندلرها
        app.add_handler(CommandHandler("start", self.game_bot.start_command))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_bot.handle_message))
        
        print("🤖 ربات شروع به کار کرد...")
        app.run_polling()
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت callback query ها"""
        query = update.callback_query
        data = query.data
        
        if data == "back_to_main":
            await self.game_bot.back_to_main(query, context)
        elif data == "view_withdrawals":
            await self.game_bot.view_withdrawals(query, context)
        elif data.startswith("reject_withdrawal_"):
            withdrawal_id = int(data.split("_")[2])
            
            cursor = self.game_bot.db.conn.cursor()
            cursor.execute('''
                UPDATE withdrawals SET status = 'rejected'
                WHERE id = ?
            ''', (withdrawal_id,))
            self.game_bot.db.conn.commit()
            
            await query.answer("❌ برداشت رد شد!")
            await self.game_bot.view_withdrawals(query, context)
        elif data == "general_stats":
            await self.show_general_stats(query, context)
        else:
            await self.game_bot.button_handler(update, context)
    
    async def show_general_stats(self, query, context):
        """نمایش آمار کلی"""
        cursor = self.game_bot.db.conn.cursor()
        
        # تعداد کاربران
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # مجموع موجودی کاربران
        cursor.execute('SELECT SUM(balance) FROM users')
        total_balance = cursor.fetchone()[0] or 0
        
        # تعداد بازی‌ها
        cursor.execute('SELECT COUNT(*) FROM games')
        total_games = cursor.fetchone()[0]
        
        # تعداد برداشت‌های معلق
        cursor.execute('SELECT COUNT(*) FROM withdrawals WHERE status = "pending"')
        pending_withdrawals = cursor.fetchone()[0]
        
        # مجموع برداشت‌های تایید شده
        cursor.execute('SELECT SUM(amount) FROM withdrawals WHERE status = "approved"')
        total_withdrawals = cursor.fetchone()[0] or 0
        
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📊 آمار کلی سیستم\n\n"
            f"👥 تعداد کاربران: {total_users:,}\n"
            f"💰 مجموع موجودی: {total_balance:,} تومان\n"
            f"🎮 تعداد بازی‌ها: {total_games:,}\n"
            f"💸 برداشت‌های معلق: {pending_withdrawals:,}\n"
            f"✅ مجموع برداشت‌ها: {total_withdrawals:,} تومان",
            reply_markup=reply_markup
        )

# تابع webhook برای PayPing
async def payping_webhook(request):
    """مدیریت webhook پرداخت"""
    try:
        data = await request.json()
        
        if data.get('status') == 'paid':
            payment_code = data.get('clientRefId')
            
            if payment_code:
                cursor = db.conn.cursor()
                cursor.execute('''
                    SELECT user_id, amount FROM payments 
                    WHERE payment_code = ? AND status = 'pending'
                ''', (payment_code,))
                result = cursor.fetchone()
                
                if result:
                    user_id, amount = result
                    
                    # تایید پرداخت
                    cursor.execute('''
                        UPDATE payments SET status = 'completed'
                        WHERE payment_code = ?
                    ''', (payment_code,))
                    
                    # اضافه کردن به موجودی
                    cursor.execute('''
                        UPDATE users SET balance = balance + ?
                        WHERE user_id = ?
                    ''', (amount, user_id))
                    
                    db.conn.commit()
                    
                    # اطلاع به کاربر
                    try:
                        bot = Application.builder().token(BOT_TOKEN).build().bot
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"✅ پرداخت شما با موفقیت انجام شد!\n\n"
                                 f"💰 مبلغ {amount:,} تومان به حساب شما اضافه شد."
                        )
                    except:
                        pass
        
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error"}

# تنظیمات بازی روزانه
async def daily_game_scheduler():
    """برنامه‌ریز بازی روزانه"""
    while True:
        now = datetime.now()
        # ساعت 22:00
        if now.hour == 22 and now.minute == 0:
            # شروع دوره جدید بازی
            bot = MathGameBot()
            app = Application.builder().token(BOT_TOKEN).build()
            
            # ارسال اطلاعیه در گروه
            await app.bot.send_message(
                chat_id=GROUP_ID,
                text="🎯 بازی ریاضی شروع شد!\n\n"
                     "🎮 برای شرکت در بازی به ربات مراجعه کنید:\n"
                     "@Maynir_Bot\n\n"
                     "⏰ زمان ثبت نام: 15 دقیقه"
            )
        
        await asyncio.sleep(60)  # چک هر دقیقه

if __name__ == "__main__":
    # اجرای ربات
    bot = TelegramBot()
    
    # راه‌اندازی scheduler
    asyncio.create_task(daily_game_scheduler())
    
    bot.run()
