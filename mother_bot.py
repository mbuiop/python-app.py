#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ربات مادر نهایی - با همه امکانات
نسخه 6.0 - پشتیبانی کامل + موتور پیشرفته + نصب کتابخانه
"""

import telebot
from telebot import types
import sqlite3
import os
import subprocess
import sys
import time
import hashlib
import json
import threading
import shutil
import re
import zipfile
import requests
import signal
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import importlib
import pkg_resources
from pathlib import Path

# ==================== تنظیمات پایه ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
FILES_DIR = os.path.join(BASE_DIR, "user_files")
RUNNING_DIR = os.path.join(BASE_DIR, "running_bots")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
RECEIPTS_DIR = os.path.join(BASE_DIR, "receipts")

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(RUNNING_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(RECEIPTS_DIR, exist_ok=True)

# ==================== توکن ربات مادر ====================
BOT_TOKEN = "8541672444:AAF4PBn7-XqiXUgaK0arVajyZfcMWqbxSJ0"
bot = telebot.TeleBot(BOT_TOKEN)
bot.delete_webhook()

# ==================== آیدی ادمین ====================
ADMIN_IDS = [327855654]  # آیدی عددی ادمین رو اینجا بزار

# ==================== شماره کارت ====================
CARD_NUMBER = "5892101187322777"
PRICE = 2000000  # 2 میلیون تومان

# ==================== لاگینگ ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(LOGS_DIR, 'mother_bot.log'),
            maxBytes=10485760,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== دیتابیس SQLite ====================
DB_PATH = os.path.join(DB_DIR, 'mother_bot.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ایجاد جداول
with get_db() as conn:
    # جدول کاربران
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            balance INTEGER DEFAULT 0,
            bots_count INTEGER DEFAULT 0,
            max_bots INTEGER DEFAULT 1,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            referrals_count INTEGER DEFAULT 0,
            verified_referrals INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            last_active TIMESTAMP
        )
    ''')
    
    # جدول ربات‌ها
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bots (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            token TEXT,
            name TEXT,
            username TEXT,
            file_path TEXT,
            folder_path TEXT,
            pid INTEGER,
            status TEXT DEFAULT 'stopped',
            created_at TIMESTAMP,
            last_active TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    ''')
    
    # جدول فیش‌های واریزی
    conn.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            receipt_path TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    # جدول ساختار پوشه‌ها
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bot_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id TEXT,
            folder_path TEXT,
            file_count INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
        )
    ''')
    
    # جدول صف ساخت
    conn.execute('''
        CREATE TABLE IF NOT EXISTS build_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            bot_id TEXT,
            folders TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    conn.commit()

# ==================== موتور کتابخانه‌ها ====================
class LibraryManager:
    """مدیریت نصب کتابخانه‌ها"""
    
    def __init__(self):
        self.common_libs = {
            # وب
            'flask': 'Flask',
            'django': 'Django',
            'fastapi': 'fastapi',
            'aiohttp': 'aiohttp',
            'requests': 'requests',
            'httpx': 'httpx',
            
            # ربات
            'pyTelegramBotAPI': 'pyTelegramBotAPI',
            'aiogram': 'aiogram',
            'python-telegram-bot': 'python-telegram-bot',
            
            # دیتابیس
            'sqlalchemy': 'SQLAlchemy',
            'sqlite3': 'sqlite3',
            'psycopg2': 'psycopg2-binary',
            'pymysql': 'pymysql',
            'redis': 'redis',
            'pymongo': 'pymongo',
            
            # علم داده
            'numpy': 'numpy',
            'pandas': 'pandas',
            'scipy': 'scipy',
            'matplotlib': 'matplotlib',
            'seaborn': 'seaborn',
            'plotly': 'plotly',
            
            # یادگیری ماشین
            'sklearn': 'scikit-learn',
            'tensorflow': 'tensorflow',
            'torch': 'torch',
            'keras': 'keras',
            'xgboost': 'xgboost',
            'lightgbm': 'lightgbm',
            
            # پردازش تصویر
            'opencv': 'opencv-python',
            'pillow': 'Pillow',
            'imageio': 'imageio',
            
            # پردازش صوت
            'pydub': 'pydub',
            'speechrecognition': 'SpeechRecognition',
            'gtts': 'gTTS',
            
            # پردازش ویدئو
            'moviepy': 'moviepy',
            'ffmpeg': 'ffmpeg-python',
            
            # وب اسکرپینگ
            'bs4': 'beautifulsoup4',
            'selenium': 'selenium',
            'scrapy': 'Scrapy',
            
            # PDF و Excel
            'pypdf2': 'PyPDF2',
            'reportlab': 'reportlab',
            'openpyxl': 'openpyxl',
            'xlsxwriter': 'XlsxWriter',
            
            # امنیت
            'cryptography': 'cryptography',
            'jwt': 'PyJWT',
            'passlib': 'passlib',
            
            # تاریخ و زمان
            'jdatetime': 'jdatetime',
            'pytz': 'pytz',
            
            # یوتیوب و دانلود
            'yt-dlp': 'yt-dlp',
            'pytube': 'pytube',
            
            # QR و بارکد
            'qrcode': 'qrcode[pil]',
            'barcode': 'python-barcode',
            
            # ایمیل و پیامک
            'smtplib': 'smtplib',
            'kavenegar': 'kavenegar',
            
            # شبکه و سوکت
            'socket': 'socket',
            'websockets': 'websockets',
            
            # سیستم
            'os': 'os',
            'sys': 'sys',
            'subprocess': 'subprocess',
            'psutil': 'psutil',
            
            # لاگینگ
            'logging': 'logging',
            'loguru': 'loguru',
            
            # تست
            'pytest': 'pytest',
            'unittest': 'unittest',
        }
        
        self.installed = self.get_installed_libs()
    
    def get_installed_libs(self):
        """دریافت لیست کتابخانه‌های نصب شده"""
        installed = {}
        for dist in pkg_resources.working_set:
            installed[dist.project_name.lower()] = dist.version
        return installed
    
    def extract_imports(self, code):
        """استخراج کتابخانه‌های import شده از کد"""
        imports = set()
        patterns = [
            r'^import\s+([a-zA-Z0-9_]+)',
            r'^from\s+([a-zA-Z0-9_]+)\s+import',
            r'__import__\([\'"]([a-zA-Z0-9_]+)[\'"]\)',
        ]
        
        for line in code.split('\n'):
            line = line.strip()
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    imports.add(match.group(1))
        
        return list(imports)
    
    def get_required_libs(self, code):
        """دریافت لیست کتابخانه‌های مورد نیاز"""
        imports = self.extract_imports(code)
        required = []
        
        for imp in imports:
            if imp in self.common_libs:
                pip_name = self.common_libs[imp]
                if pip_name.lower() not in self.installed:
                    required.append({
                        'name': imp,
                        'pip': pip_name,
                        'status': 'not_installed'
                    })
                else:
                    required.append({
                        'name': imp,
                        'pip': pip_name,
                        'status': 'installed',
                        'version': self.installed[pip_name.lower()]
                    })
        
        return required
    
    def install_library(self, lib_name):
        """نصب کتابخانه"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", lib_name],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.installed = self.get_installed_libs()
                return True, "نصب شد"
            else:
                return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "زمان نصب بیش از حد طول کشید"
        except Exception as e:
            return False, str(e)
    
    def install_all_required(self, code):
        """نصب همه کتابخانه‌های مورد نیاز"""
        required = self.get_required_libs(code)
        results = []
        
        for lib in required:
            if lib['status'] == 'not_installed':
                success, msg = self.install_library(lib['pip'])
                results.append({
                    'name': lib['name'],
                    'success': success,
                    'message': msg
                })
        
        return results
    
    def install_user_library(self, lib_name, chat_id):
        """نصب کتابخانه درخواستی کاربر"""
        try:
            msg = bot.send_message(chat_id, f"🔄 در حال نصب {lib_name}...")
            
            success, result = self.install_library(lib_name)
            
            if success:
                bot.edit_message_text(
                    f"✅ کتابخانه {lib_name} با موفقیت نصب شد.",
                    chat_id,
                    msg.message_id
                )
                return True
            else:
                bot.edit_message_text(
                    f"❌ خطا در نصب {lib_name}:\n{result[:200]}",
                    chat_id,
                    msg.message_id
                )
                return False
        except Exception as e:
            bot.send_message(chat_id, f"❌ خطا: {str(e)}")
            return False

library_manager = LibraryManager()

# ==================== موتور اجرای پیشرفته ====================
class AdvancedBotEngine:
    """موتور اجرای پیشرفته ربات‌ها"""
    
    def __init__(self):
        self.running_processes = {}
        self.lock = threading.Lock()
    
    def prepare_code(self, code):
        """آماده‌سازی کد برای اجرا"""
        # اگر تابع main نداره، اضافه کن
        if 'def main' not in code and 'if __name__ == "__main__"' not in code:
            if 'bot.infinity_polling' in code:
                code += '\n\nif __name__ == "__main__":\n    print("✅ ربات در حال اجراست...")\n    bot.infinity_polling()\n'
        return code
    
    def run_bot(self, bot_id, user_id, code, token):
        """اجرای ربات"""
        result = {
            'success': False,
            'pid': None,
            'error': None
        }
        
        try:
            # آماده‌سازی کد
            code = self.prepare_code(code)
            
            # ایجاد پوشه برای ربات
            bot_run_dir = os.path.join(RUNNING_DIR, bot_id)
            os.makedirs(bot_run_dir, exist_ok=True)
            
            # ذخیره کد ربات
            bot_file = os.path.join(bot_run_dir, f"{bot_id}.py")
            with open(bot_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # ذخیره توکن
            token_file = os.path.join(bot_run_dir, "token.txt")
            with open(token_file, 'w') as f:
                f.write(token)
            
            # فایل لاگ
            log_file = os.path.join(bot_run_dir, "bot.log")
            
            # اجرا
            process = subprocess.Popen(
                [sys.executable, bot_file],
                stdout=open(log_file, 'a'),
                stderr=subprocess.STDOUT,
                cwd=bot_run_dir,
                start_new_session=True
            )
            
            # ذخیره اطلاعات
            with self.lock:
                self.running_processes[bot_id] = {
                    'process': process,
                    'dir': bot_run_dir,
                    'pid': process.pid,
                    'start_time': time.time()
                }
            
            # صبر برای بررسی خطا
            time.sleep(2)
            
            if process.poll() is None:
                result['success'] = True
                result['pid'] = process.pid
            else:
                # خطا رو بخون
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        result['error'] = f.read()[-500:]
                else:
                    result['error'] = "خطای ناشناخته"
                    
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def stop_bot(self, bot_id):
        """توقف ربات"""
        with self.lock:
            if bot_id in self.running_processes:
                try:
                    pid = self.running_processes[bot_id]['pid']
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                    time.sleep(1)
                    
                    if bot_id in self.running_processes:
                        del self.running_processes[bot_id]
                    return True
                except:
                    pass
        return False
    
    def get_status(self, bot_id):
        """وضعیت ربات"""
        with self.lock:
            if bot_id in self.running_processes:
                process = self.running_processes[bot_id]['process']
                if process.poll() is None:
                    return {'running': True, 'pid': process.pid}
        return {'running': False}

bot_engine = AdvancedBotEngine()

# ==================== توابع کمکی ====================

def get_user(user_id):
    with get_db() as conn:
        user = conn.execute(
            'SELECT * FROM users WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        return dict(user) if user else None

def create_user(user_id, username, first_name, last_name, referred_by=None):
    with get_db() as conn:
        now = datetime.now().isoformat()
        
        # تولید کد رفرال یکتا
        referral_code = hashlib.md5(f"{user_id}_{time.time()}".encode()).hexdigest()[:8]
        
        conn.execute('''
            INSERT OR IGNORE INTO users 
            (user_id, username, first_name, last_name, referral_code, referred_by, created_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, referral_code, referred_by, now, now))
        
        conn.execute('''
            UPDATE users SET last_active = ? WHERE user_id = ?
        ''', (now, user_id))
        conn.commit()
        
        # اگه کاربر با رفرال اومده بود
        if referred_by:
            conn.execute('''
                UPDATE users SET referrals_count = referrals_count + 1
                WHERE user_id = ?
            ''', (referred_by,))
            conn.commit()

def check_payment(user_id):
    """بررسی وضعیت پرداخت کاربر"""
    with get_db() as conn:
        # بررسی فیش‌های تایید شده
        receipt = conn.execute('''
            SELECT id FROM receipts 
            WHERE user_id = ? AND status = 'approved'
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,)).fetchone()
        
        return receipt is not None

def check_bot_limit(user_id):
    """بررسی محدودیت تعداد ربات برای کاربر بر اساس رفرال"""
    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user:
            return True, 1, 0
        
        # هر ۵ نفر رفرال verified = ۱ ربات اضافه
        extra_bots = user['verified_referrals'] // 5
        max_bots = 1 + extra_bots
        
        current_bots = conn.execute('SELECT COUNT(*) FROM bots WHERE user_id = ?', (user_id,)).fetchone()[0]
        
        return current_bots < max_bots, max_bots, current_bots

def add_bot(user_id, bot_id, token, name, username, file_path, folder_path=None, pid=None):
    with get_db() as conn:
        now = datetime.now().isoformat()
        status = 'running' if pid else 'stopped'
        conn.execute('''
            INSERT INTO bots (id, user_id, token, name, username, file_path, folder_path, pid, status, created_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (bot_id, user_id, token, name, username, file_path, folder_path, pid, status, now, now))
        
        conn.execute('''
            UPDATE users SET bots_count = bots_count + 1, last_active = ?
            WHERE user_id = ?
        ''', (now, user_id))
        conn.commit()
        
        # به‌روزرسانی رفرال‌های verified
        user = conn.execute('SELECT referred_by FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if user and user['referred_by']:
            conn.execute('''
                UPDATE users SET verified_referrals = verified_referrals + 1
                WHERE user_id = ?
            ''', (user['referred_by'],))
            conn.commit()
        
        return True

def get_user_bots(user_id):
    with get_db() as conn:
        bots = conn.execute('''
            SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,)).fetchall()
        return [dict(bot) for bot in bots]

def get_bot(bot_id):
    with get_db() as conn:
        bot = conn.execute('SELECT * FROM bots WHERE id = ?', (bot_id,)).fetchone()
        return dict(bot) if bot else None

def update_bot_status(bot_id, status, pid=None):
    with get_db() as conn:
        if pid:
            conn.execute('''
                UPDATE bots SET status = ?, pid = ?, last_active = ? WHERE id = ?
            ''', (status, pid, datetime.now().isoformat(), bot_id))
        else:
            conn.execute('''
                UPDATE bots SET status = ?, last_active = ? WHERE id = ?
            ''', (status, datetime.now().isoformat(), bot_id))
        conn.commit()

def delete_bot(bot_id, user_id):
    """حذف کامل ربات"""
    with get_db() as conn:
        bot = conn.execute('SELECT * FROM bots WHERE id = ? AND user_id = ?', (bot_id, user_id)).fetchone()
        if not bot:
            return False
        
        # توقف ربات
        if bot['pid']:
            bot_engine.stop_bot(bot_id)
        
        # حذف فایل‌ها
        if bot['file_path'] and os.path.exists(bot['file_path']):
            os.remove(bot['file_path'])
        
        if bot['folder_path'] and os.path.exists(bot['folder_path']):
            shutil.rmtree(bot['folder_path'])
        
        # حذف از دیتابیس
        conn.execute('DELETE FROM bots WHERE id = ?', (bot_id,))
        conn.execute('UPDATE users SET bots_count = bots_count - 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        return True

def extract_token_from_code(code):
    patterns = [
        r'token\s*=\s*["\']([^"\']+)["\']',
        r'TOKEN\s*=\s*["\']([^"\']+)["\']',
        r'API_TOKEN\s*=\s*["\']([^"\']+)["\']',
        r'BOT_TOKEN\s*=\s*["\']([^"\']+)["\']',
        r'bot\s*=\s*telebot\.TeleBot\(\s*["\']([^"\']+)["\']\s*\)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, code, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def validate_python_code(code):
    try:
        compile(code, '<string>', 'exec')
        return True, None
    except SyntaxError as e:
        return False, str(e)

def save_uploaded_file(user_id, file_data, file_name):
    user_dir = os.path.join(FILES_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    
    timestamp = int(time.time())
    file_path = os.path.join(user_dir, f"{timestamp}_{file_name}")
    
    with open(file_path, 'wb') as f:
        f.write(file_data)
    
    return file_path

def extract_files_from_zip(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    
    py_files = []
    for root, _, files in os.walk(extract_to):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                py_files.append({
                    'name': file,
                    'path': file_path,
                    'content': content
                })
    
    return py_files

# ==================== مانیتورینگ ربات‌ها ====================
def monitor_running_bots():
    """بررسی ربات‌های در حال اجرا"""
    while True:
        try:
            with get_db() as conn:
                running_bots = conn.execute('SELECT id, pid FROM bots WHERE status = "running"').fetchall()
                
                for bot in running_bots:
                    bot_id, pid = bot
                    status = bot_engine.get_status(bot_id)
                    
                    if not status['running']:
                        conn.execute('UPDATE bots SET status = ? WHERE id = ?', ('stopped', bot_id))
                        conn.commit()
                        logger.info(f"⚠️ ربات {bot_id} متوقف شد")
            
            time.sleep(30)  # هر ۳۰ ثانیه چک کن
            
        except Exception as e:
            logger.error(f"خطا در مانیتورینگ: {e}")
            time.sleep(60)

# شروع مانیتورینگ در یک نخ جدا
monitor_thread = threading.Thread(target=monitor_running_bots, daemon=True)
monitor_thread.start()

# ==================== آمار ====================
start_time = datetime.now()
total_requests = 0
total_bots_created = 0

# ==================== منوی اصلی ====================
def get_main_menu(is_admin=False):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    buttons = [
        types.KeyboardButton('🤖 ساخت ربات جدید'),
        types.KeyboardButton('📋 ربات‌های من'),
        types.KeyboardButton('🔄 فعال/غیرفعال کردن ربات'),
        types.KeyboardButton('🗑 حذف ربات'),
        types.KeyboardButton('💰 کیف پول و رفرال'),
        types.KeyboardButton('📚 راهنمای کامل (۵۰ خط)'),
        types.KeyboardButton('📦 نصب کتابخانه'),
        types.KeyboardButton('📊 آمار'),
        types.KeyboardButton('📞 پشتیبانی')
    ]
    
    if is_admin:
        buttons.append(types.KeyboardButton('👑 پنل ادمین'))
    
    markup.add(*buttons)
    return markup

# ==================== هندلرهای ربات ====================

@bot.message_handler(commands=['start'])
def cmd_start(message):
    global total_requests
    total_requests += 1
    
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    
    # بررسی کد رفرال
    referred_by = None
    args = message.text.split()
    if len(args) > 1:
        ref_code = args[1]
        with get_db() as conn:
            referrer = conn.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref_code,)).fetchone()
            if referrer:
                referred_by = referrer['user_id']
    
    create_user(user_id, username, first_name, last_name, referred_by)
    
    is_admin = user_id in ADMIN_IDS
    markup = get_main_menu(is_admin)
    
    welcome_text = (
        f"🚀 **به ربات مادر نهایی خوش آمدید {first_name}!**\n\n"
        f"👤 آیدی شما: `{user_id}`\n"
        f"🎁 کد رفرال شما: `{get_user(user_id)['referral_code']}`\n\n"
        f"📤 فایل `.py` خود را آپلود کنید تا رباتتان ساخته و اجرا شود.\n"
        f"💡 برای راهنمایی کامل، گزینه '📚 راهنمای کامل (۵۰ خط)' را بزنید."
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == '📚 راهنمای کامل (۵۰ خط)')
def full_guide(message):
    user = get_user(message.from_user.id)
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start={user['referral_code']}"
    
    text = (
        "📚 **راهنمای کامل استفاده از ربات مادر**\n\n"
        "═══════════════════════════════════\n\n"
        
        "**1️⃣ ساخت ربات جدید**\n"
        "• فایل `.py` یا `.zip` خود را آپلود کنید\n"
        "• می‌توانید چندین فایل در یک پوشه zip کنید\n"
        "• حجم فایل حداکثر ۵۰ مگابایت\n"
        "• توکن باید داخل کد باشه (TOKEN = '...')\n\n"
        
        "**2️⃣ ساختار پوشه‌ها**\n"
        "• اگر پروژه شما چند پوشه دارد:\n"
        "  - اول پوشه اصلی رو بسازید\n"
        "  - فایل‌ها رو در پوشه‌ها قرار دهید\n"
        "  - بعد از اتمام، گزینه ساخت ربات را بزنید\n\n"
        
        "**3️⃣ کتابخانه‌ها**\n"
        "• ۶۰+ کتابخانه پرکاربرد پشتیبانی می‌شود\n"
        "• کتابخانه‌های مورد نیاز کد شما به صورت خودکار نصب می‌شوند\n"
        "• می‌توانید از منوی '📦 نصب کتابخانه' کتابخانه دلخواه نصب کنید\n\n"
        
        "**4️⃣ مدیریت ربات‌ها**\n"
        "• /start - شروع و منوی اصلی\n"
        "• /bots - لیست ربات‌های شما\n"
        "• /stop [bot_id] - توقف یک ربات\n"
        "• /resume [bot_id] - راه‌اندازی مجدد ربات\n"
        "• /delete [bot_id] - حذف کامل ربات\n\n"
        
        "**5️⃣ سیستم رفرال**\n"
        "• هر کاربر یک کد رفرال اختصاصی دارد\n"
        "• با دعوت دوستان، ربات اضافه می‌گیرید\n"
        "• هر ۵ نفر که ربات بسازند = ۱ ربات اضافه\n"
        f"• کد رفرال شما: `{user['referral_code']}`\n"
        f"• لینک دعوت: {referral_link}\n\n"
        
        "**6️⃣ خرید و فعال‌سازی**\n"
        f"• هزینه ساخت هر ربات: {PRICE:,} تومان\n"
        f"• شماره کارت: `{CARD_NUMBER}`\n"
        "• پس از واریز، فیش را ارسال کنید\n"
        "• فیش شما توسط ادمین بررسی می‌شود\n\n"
        
        "**7️⃣ دستورات ویژه ادمین**\n"
        "• /admin - پنل ادمین\n"
        "• /broadcast [متن] - ارسال پیام همگانی\n"
        "• /users - آمار کاربران\n"
        "• /receipts - مشاهده فیش‌ها\n"
        "• /delete_user [user_id] - حذف کاربر\n\n"
        
        "**8️⃣ نکات مهم**\n"
        "• قبل از آپلود، کد خود را تست کنید\n"
        "• توکن باید در کد تعریف شده باشد\n"
        "• هر ربات در یک فرآیند جدا اجرا می‌شود\n"
        "• در صورت مشکل، با پشتیبانی تماس بگیرید\n\n"
        
        "═══════════════════════════════════\n"
        "📞 **پشتیبانی:** @shahraghee13\n"
        "═══════════════════════════════════"
    )
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == '💰 کیف پول و رفرال')
def wallet_ref(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    paid = check_payment(user_id)
    can_create, max_bots, current_bots = check_bot_limit(user_id)
    
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start={user['referral_code']}"
    
    text = (
        f"💰 **کیف پول و سیستم رفرال**\n\n"
        f"👤 کاربر: {user['first_name']}\n"
        f"🆔 آیدی: `{user_id}`\n\n"
        f"💳 **وضعیت پرداخت:**\n"
        f"{'✅ تایید شده' if paid else '⏳ در انتظار تایید'}\n\n"
        f"🎁 **کد رفرال شما:**\n"
        f"`{user['referral_code']}`\n"
        f"🔗 لینک دعوت:\n"
        f"{referral_link}\n\n"
        f"📊 **آمار رفرال:**\n"
        f"• کلیک‌ها: {user['referrals_count']}\n"
        f"• ساخته شده: {user['verified_referrals']}\n\n"
        f"🤖 **ربات‌ها:**\n"
        f"• فعلی: {current_bots}\n"
        f"• حداکثر: {max_bots}\n"
        f"• هر ۵ نفر که ربات بسازند = ۱ ربات اضافه\n\n"
    )
    
    if not paid:
        text += (
            f"💳 **برای ساخت ربات جدید:**\n"
            f"کارت به نام: ....\n"
            f"شماره کارت: `{CARD_NUMBER}`\n"
            f"مبلغ: {PRICE:,} تومان\n\n"
            f"📸 پس از واریز، تصویر فیش را ارسال کنید.\n"
            f"فیش شما توسط ادمین بررسی می‌شود."
        )
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    user_id = message.from_user.id
    
    # دریافت عکس
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # ذخیره فیش
    receipt_path = os.path.join(RECEIPTS_DIR, f"{user_id}_{int(time.time())}.jpg")
    with open(receipt_path, 'wb') as f:
        f.write(downloaded_file)
    
    # ذخیره در دیتابیس
    with get_db() as conn:
        conn.execute('''
            INSERT INTO receipts (user_id, amount, receipt_path, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, PRICE, receipt_path, datetime.now().isoformat()))
        conn.commit()
    
    bot.reply_to(
        message,
        f"✅ فیش واریزی شما دریافت شد.\n"
        f"💰 مبلغ: {PRICE:,} تومان\n"
        f"🆔 کد پیگیری: {int(time.time())}\n\n"
        f"پس از بررسی توسط ادمین، ربات شما فعال می‌شود.\n"
        f"📞 پیگیری: @shahraghee13"
    )
    
    # اطلاع به ادمین
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(
                admin_id,
                f"📸 **فیش جدید واریزی**\n\n"
                f"👤 کاربر: {user_id}\n"
                f"💰 مبلغ: {PRICE:,} تومان\n"
                f"🕐 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"برای بررسی به پنل ادمین بروید."
            )
        except:
            pass

@bot.message_handler(func=lambda m: m.text == '📦 نصب کتابخانه')
def install_library_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    libs = [
        ('requests', 'requests'),
        ('numpy', 'numpy'),
        ('pandas', 'pandas'),
        ('flask', 'flask'),
        ('django', 'django'),
        ('pillow', 'Pillow'),
        ('beautifulsoup4', 'beautifulsoup4'),
        ('selenium', 'selenium'),
        ('pyTelegramBotAPI', 'pyTelegramBotAPI'),
        ('aiogram', 'aiogram'),
        ('jdatetime', 'jdatetime'),
        ('🔧 دستی', 'custom')
    ]
    
    for name, data in libs:
        markup.add(types.InlineKeyboardButton(name, callback_data=f"lib_{data}"))
    
    bot.send_message(
        message.chat.id,
        "📦 **کتابخانه مورد نظر را انتخاب کنید:**",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('lib_'))
def install_library_callback(call):
    lib = call.data.replace('lib_', '')
    
    if lib == 'custom':
        msg = bot.send_message(
            call.message.chat.id,
            "📦 **نام کتابخانه را وارد کنید:**"
        )
        bot.register_next_step_handler(msg, install_custom_library)
        return
    
    bot.answer_callback_query(call.id, f"در حال نصب {lib}...")
    library_manager.install_user_library(lib, call.message.chat.id)

def install_custom_library(message):
    lib = message.text.strip()
    library_manager.install_user_library(lib, message.chat.id)

@bot.message_handler(func=lambda m: m.text == '🔄 فعال/غیرفعال کردن ربات')
def toggle_bot_prompt(message):
    user_id = message.from_user.id
    bots = get_user_bots(user_id)
    
    if not bots:
        bot.send_message(message.chat.id, "📋 شما رباتی ندارید!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b in bots:
        status = "🟢" if b['status'] == 'running' else "🔴"
        btn = types.InlineKeyboardButton(
            f"{status} {b['name']}",
            callback_data=f"toggle_{b['id']}"
        )
        markup.add(btn)
    
    bot.send_message(
        message.chat.id,
        "🔄 **فعال/غیرفعال کردن ربات**\n\n"
        "ربات مورد نظر را انتخاب کنید:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_'))
def toggle_bot(call):
    bot_id = call.data.replace('toggle_', '')
    user_id = call.from_user.id
    
    bot_info = get_bot(bot_id)
    
    if not bot_info or bot_info['user_id'] != user_id:
        bot.answer_callback_query(call.id, "❌ ربات پیدا نشد!")
        return
    
    if bot_info['status'] == 'running':
        # توقف ربات
        if bot_engine.stop_bot(bot_id):
            update_bot_status(bot_id, 'stopped')
            bot.answer_callback_query(call.id, "✅ ربات متوقف شد")
            
            # درخواست توکن برای فعال‌سازی مجدد
            msg = bot.send_message(
                call.message.chat.id,
                "🔑 **برای فعال‌سازی مجدد، توکن ربات را ارسال کنید:**"
            )
            bot.register_next_step_handler(msg, resume_bot, bot_id)
        else:
            bot.answer_callback_query(call.id, "❌ خطا در توقف ربات!")
    
    else:
        # ربات متوقف است - درخواست توکن
        msg = bot.send_message(
            call.message.chat.id,
            f"🔑 **برای فعال‌سازی ربات {bot_info['name']}، توکن را ارسال کنید:**"
        )
        bot.register_next_step_handler(msg, resume_bot, bot_id)

def resume_bot(message, bot_id):
    token = message.text.strip()
    user_id = message.from_user.id
    
    try:
        # تست توکن
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
        if response.status_code != 200:
            bot.reply_to(message, "❌ توکن معتبر نیست!")
            return
        
        bot_info = response.json()['result']
        
        # خوندن کد قبلی
        bot_data = get_bot(bot_id)
        if not bot_data:
            bot.reply_to(message, "❌ ربات پیدا نشد!")
            return
        
        with open(bot_data['file_path'], 'r', encoding='utf-8') as f:
            code = f.read()
        
        # اجرای مجدد
        result = bot_engine.run_bot(bot_id, user_id, code, token)
        
        if result['success']:
            update_bot_status(bot_id, 'running', result['pid'])
            bot.reply_to(
                message,
                f"✅ ربات {bot_info['first_name']} با موفقیت فعال شد!\n"
                f"🔗 https://t.me/{bot_info['username']}"
            )
        else:
            bot.reply_to(message, f"❌ خطا در اجرای ربات: {result.get('error', '')}")
            
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {str(e)}")

@bot.message_handler(func=lambda m: m.text == '🗑 حذف ربات')
def delete_bot_prompt(message):
    user_id = message.from_user.id
    bots = get_user_bots(user_id)
    
    if not bots:
        bot.send_message(message.chat.id, "📋 شما رباتی ندارید!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b in bots:
        btn = types.InlineKeyboardButton(
            f"🗑 {b['name']}",
            callback_data=f"delete_{b['id']}"
        )
        markup.add(btn)
    
    bot.send_message(
        message.chat.id,
        "⚠️ **حذف ربات**\n\n"
        "⚠️ توجه: پس از حذف، امکان بازیابی وجود ندارد!\n\n"
        "ربات مورد نظر را انتخاب کنید:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def confirm_delete(call):
    bot_id = call.data.replace('delete_', '')
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"confirm_delete_{bot_id}")
    btn2 = types.InlineKeyboardButton("❌ انصراف", callback_data="cancel_delete")
    markup.add(btn1, btn2)
    
    bot.edit_message_text(
        "⚠️ **آیا از حذف این ربات اطمینان دارید؟**\n"
        "این عمل غیرقابل بازگشت است!",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_'))
def do_delete(call):
    bot_id = call.data.replace('confirm_delete_', '')
    user_id = call.from_user.id
    
    if delete_bot(bot_id, user_id):
        bot.edit_message_text(
            "✅ ربات با موفقیت حذف شد.",
            call.message.chat.id,
            call.message.message_id
        )
    else:
        bot.edit_message_text(
            "❌ خطا در حذف ربات!",
            call.message.chat.id,
            call.message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_delete')
def cancel_delete(call):
    bot.edit_message_text(
        "❌ عملیات حذف لغو شد.",
        call.message.chat.id,
        call.message.message_id
    )

@bot.message_handler(commands=['bots'])
def cmd_bots(message):
    user_id = message.from_user.id
    bots = get_user_bots(user_id)
    
    if not bots:
        bot.send_message(
            message.chat.id,
            "📋 شما هنوز رباتی نساخته‌اید!"
        )
        return
    
    for b in bots[:5]:
        status_emoji = "🟢" if b['status'] == 'running' else "🔴"
        text = f"{status_emoji} **{b['name']}**\n"
        text += f"🔗 https://t.me/{b['username']}\n"
        text += f"🆔 `{b['id']}`\n"
        text += f"📊 وضعیت: {b['status']}\n"
        if b['pid']:
            text += f"🔄 PID: {b['pid']}\n"
        text += f"📅 {b['created_at'][:10]}\n"
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ لطفاً آیدی ربات را وارد کنید:\n/stop bot_id")
        return
    
    bot_id = parts[1]
    user_id = message.from_user.id
    
    bot_info = get_bot(bot_id)
    
    if not bot_info or bot_info['user_id'] != user_id:
        bot.reply_to(message, "❌ ربات پیدا نشد یا مالک آن نیستید!")
        return
    
    if bot_info['status'] != 'running':
        bot.reply_to(message, "❌ این ربات در حال اجرا نیست!")
        return
    
    if bot_engine.stop_bot(bot_id):
        update_bot_status(bot_id, 'stopped')
        bot.reply_to(message, f"✅ ربات {bot_info['name']} متوقف شد.\n"
                              f"برای فعال‌سازی مجدد، از منوی اصلی گزینه '🔄 فعال/غیرفعال کردن ربات' را بزنید.")
    else:
        bot.reply_to(message, "❌ خطا در توقف ربات!")

@bot.message_handler(commands=['resume'])
def cmd_resume(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ لطفاً آیدی ربات را وارد کنید:\n/resume bot_id")
        return
    
    bot_id = parts[1]
    user_id = message.from_user.id
    
    bot_info = get_bot(bot_id)
    
    if not bot_info or bot_info['user_id'] != user_id:
        bot.reply_to(message, "❌ ربات پیدا نشد یا مالک آن نیستید!")
        return
    
    msg = bot.reply_to(message, f"🔑 توکن ربات {bot_info['name']} را ارسال کنید:")
    bot.register_next_step_handler(msg, resume_bot, bot_id)

@bot.message_handler(func=lambda m: m.text == '🤖 ساخت ربات جدید')
def new_bot(message):
    user_id = message.from_user.id
    
    # بررسی پرداخت
    if not check_payment(user_id):
        bot.send_message(
            message.chat.id,
            f"❌ برای ساخت ربات باید ابتدا هزینه را پرداخت کنید.\n\n"
            f"💰 مبلغ: {PRICE:,} تومان\n"
            f"💳 شماره کارت: `{CARD_NUMBER}`\n\n"
            f"📸 پس از واریز، تصویر فیش را ارسال کنید.\n"
            f"یا از منوی '💰 کیف پول و رفرال' اقدام کنید."
        )
        return
    
    can_create, max_bots, current_bots = check_bot_limit(user_id)
    
    if not can_create:
        bot.send_message(
            message.chat.id,
            f"❌ شما به حداکثر تعداد ربات ({max_bots}) رسیده‌اید!\n\n"
            f"برای ساخت ربات جدید:\n"
            f"1️⃣ یکی از ربات‌های فعلی را حذف کنید\n"
            f"2️⃣ یا با دعوت دوستان، ربات اضافه بگیرید\n\n"
            f"رفرال‌های شما: {get_user(user_id)['verified_referrals']}"
        )
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton("📁 آپلود مستقیم فایل", callback_data="build_simple")
    btn2 = types.InlineKeyboardButton("📂 ساخت با پوشه‌های چندتایی", callback_data="build_folder")
    markup.add(btn1, btn2)
    
    bot.send_message(
        message.chat.id,
        "🤖 **ساخت ربات جدید**\n\n"
        "روش ساخت را انتخاب کنید:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "build_simple")
def build_simple(call):
    bot.send_message(
        call.message.chat.id,
        "📤 **آپلود فایل**\n\n"
        "فایل `.py` یا `.zip` خود را ارسال کنید:\n\n"
        "✅ توکن باید داخل کد باشه\n"
        "✅ کتابخانه‌های مورد نیاز خودکار نصب می‌شوند\n"
        "✅ حجم فایل حداکثر ۵۰ مگابایت"
    )

@bot.callback_query_handler(func=lambda call: call.data == "build_folder")
def build_folder(call):
    user_id = call.from_user.id
    
    # ایجاد یک ربات موقت برای ساخت پوشه‌ها
    temp_bot_id = hashlib.md5(f"temp_{user_id}_{time.time()}".encode()).hexdigest()[:10]
    temp_folder = os.path.join(FILES_DIR, str(user_id), "temp_build", temp_bot_id)
    os.makedirs(temp_folder, exist_ok=True)
    
    # ذخیره در صف ساخت
    with get_db() as conn:
        conn.execute('''
            INSERT INTO build_queue (user_id, bot_id, folders, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, temp_bot_id, json.dumps([]), datetime.now().isoformat()))
        conn.commit()
    
    bot.send_message(
        call.message.chat.id,
        f"📂 **ساخت با پوشه‌های چندتایی**\n\n"
        f"🆔 شناسه ساخت: `{temp_bot_id}`\n\n"
        f"**مراحل:**\n"
        f"1️⃣ برای هر پوشه، گزینه '➕ پوشه جدید' را بزنید\n"
        f"2️⃣ نام پوشه را وارد کنید\n"
        f"3️⃣ فایل‌های مربوط به آن پوشه را آپلود کنید\n"
        f"4️⃣ بعد از اتمام هر پوشه، گزینه '✅ ذخیره پوشه' را بزنید\n"
        f"5️⃣ در پایان، گزینه '🚀 ساخت ربات' را بزنید\n\n"
        f"🔽 از دکمه‌های زیر استفاده کنید:",
        reply_markup=get_folder_builder_markup(temp_bot_id)
    )

def get_folder_builder_markup(temp_bot_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ پوشه جدید", callback_data=f"add_folder_{temp_bot_id}"),
        types.InlineKeyboardButton("📋 لیست پوشه‌ها", callback_data=f"list_folders_{temp_bot_id}"),
        types.InlineKeyboardButton("✅ ذخیره پوشه فعلی", callback_data=f"save_folder_{temp_bot_id}"),
        types.InlineKeyboardButton("🚀 ساخت ربات", callback_data=f"build_now_{temp_bot_id}"),
        types.InlineKeyboardButton("❌ انصراف", callback_data="cancel_build")
    )
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_folder_'))
def add_folder(call):
    temp_bot_id = call.data.replace('add_folder_', '')
    
    msg = bot.send_message(
        call.message.chat.id,
        "📂 **نام پوشه جدید را وارد کنید:**\n"
        "(مثال: modules, utils, handlers)"
    )
    bot.register_next_step_handler(msg, process_folder_name, temp_bot_id)

def process_folder_name(message, temp_bot_id):
    folder_name = message.text.strip()
    user_id = message.from_user.id
    
    # ذخیره در صف ساخت
    with get_db() as conn:
        queue = conn.execute('SELECT folders FROM build_queue WHERE bot_id = ?', (temp_bot_id,)).fetchone()
        if queue:
            folders = json.loads(queue['folders'])
            folders.append({
                'name': folder_name,
                'files': [],
                'status': 'pending'
            })
            conn.execute('UPDATE build_queue SET folders = ? WHERE bot_id = ?', 
                        (json.dumps(folders), temp_bot_id))
            conn.commit()
    
    bot.send_message(
        message.chat.id,
        f"✅ پوشه `{folder_name}` ایجاد شد.\n"
        f"اکنون فایل‌های مربوط به این پوشه را آپلود کنید.\n"
        f"بعد از اتمام، گزینه '✅ ذخیره پوشه فعلی' را بزنید.",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('save_folder_'))
def save_folder(call):
    temp_bot_id = call.data.replace('save_folder_', '')
    user_id = call.from_user.id
    
    bot.send_message(
        call.message.chat.id,
        "📤 **فایل‌های این پوشه را آپلود کنید**\n\n"
        "✅ می‌توانید چندین فایل ارسال کنید\n"
        "✅ بعد از اتمام، دستور /done را بزنید"
    )
    
    # ذخیره وضعیت برای دریافت فایل‌ها
    user_data[f"folder_{user_id}"] = {
        'bot_id': temp_bot_id,
        'files': []
    }

user_data = {}

@bot.message_handler(content_types=['document'])
def handle_build_file(message):
    user_id = message.from_user.id
    
    if f"folder_{user_id}" in user_data:
        # ساخت با پوشه
        handle_folder_build(message)
        return
    
    # ساخت عادی
    handle_normal_build(message)

def handle_folder_build(message):
    user_id = message.from_user.id
    data = user_data[f"folder_{user_id}"]
    file_name = message.document.file_name
    
    if not file_name.endswith('.py'):
        bot.reply_to(message, "❌ فقط فایل‌های `.py` مجاز هستند!")
        return
    
    # ذخیره فایل
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    file_path = save_uploaded_file(user_id, downloaded_file, file_name)
    
    data['files'].append({
        'name': file_name,
        'path': file_path
    })
    
    bot.reply_to(message, f"✅ فایل {file_name} ذخیره شد.")

def handle_normal_build(message):
    # کد قبلی برای ساخت عادی
    global total_requests, total_bots_created
    total_requests += 1
    
    user_id = message.from_user.id
    file_name = message.document.file_name
    
    # بررسی پرداخت
    if not check_payment(user_id):
        bot.reply_to(message, "❌ ابتدا هزینه را پرداخت کنید!")
        return
    
    can_create, max_bots, current_bots = check_bot_limit(user_id)
    if not can_create:
        bot.reply_to(message, "❌ شما به حد مجاز ربات رسیده‌اید!")
        return
    
    if not (file_name.endswith('.py') or file_name.endswith('.zip')):
        bot.reply_to(message, "❌ فقط فایل‌های `.py` یا `.zip` مجاز هستند!")
        return
    
    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ حجم فایل نباید بیشتر از ۵۰ مگابایت باشد!")
        return
    
    status_msg = bot.reply_to(message, "🔄 در حال پردازش فایل...")
    
    try:
        # دانلود فایل
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # ذخیره فایل
        file_path = save_uploaded_file(user_id, downloaded_file, file_name)
        
        files_content = {}
        main_code = ""
        
        if file_name.endswith('.zip'):
            # استخراج فایل‌های zip
            extract_dir = os.path.join(FILES_DIR, str(user_id), f"extract_{int(time.time())}")
            os.makedirs(extract_dir, exist_ok=True)
            
            py_files = extract_files_from_zip(file_path, extract_dir)
            for pf in py_files:
                files_content[pf['name']] = pf['content']
                if pf['name'] == 'bot.py' or pf['name'] == 'main.py':
                    main_code = pf['content']
            
            shutil.rmtree(extract_dir)
            
            if not main_code and py_files:
                main_code = py_files[0]['content']
        
        else:  # فایل .py
            with open(file_path, 'r', encoding='utf-8') as f:
                main_code = f.read()
            files_content[file_name] = main_code
        
        if not main_code:
            bot.edit_message_text(
                "❌ هیچ فایل پایتونی پیدا نشد!",
                message.chat.id,
                status_msg.message_id
            )
            return
        
        # اعتبارسنجی کد
        is_valid, error = validate_python_code(main_code)
        if not is_valid:
            bot.edit_message_text(
                f"❌ خطای نحوی در کد:\n```\n{error}\n```",
                message.chat.id,
                status_msg.message_id,
                parse_mode="Markdown"
            )
            return
        
        # استخراج توکن
        token = extract_token_from_code(main_code)
        if not token:
            bot.edit_message_text(
                "❌ توکن در کد پیدا نشد!\n"
                "مثال: TOKEN = '123456:ABCdef'",
                message.chat.id,
                status_msg.message_id
            )
            return
        
        # تست توکن
        try:
            response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
            if response.status_code != 200:
                bot.edit_message_text(
                    "❌ توکن معتبر نیست!",
                    message.chat.id,
                    status_msg.message_id
                )
                return
            
            bot_info = response.json()['result']
            bot_name = bot_info['first_name']
            bot_username = bot_info['username']
            
        except Exception as e:
            bot.edit_message_text(
                f"❌ خطا در بررسی توکن: {str(e)}",
                message.chat.id,
                status_msg.message_id
            )
            return
        
        # نصب کتابخانه‌های مورد نیاز
        bot.edit_message_text(
            "📦 در حال نصب کتابخانه‌های مورد نیاز...",
            message.chat.id,
            status_msg.message_id
        )
        
        install_results = library_manager.install_all_required(main_code)
        
        # آیدی یکتا برای ربات
        bot_id = hashlib.md5(f"{user_id}_{token}_{time.time()}".encode()).hexdigest()[:10]
        
        bot.edit_message_text(
            f"🚀 در حال اجرای ربات...",
            message.chat.id,
            status_msg.message_id
        )
        
        # اجرای ربات با موتور پیشرفته
        result = bot_engine.run_bot(bot_id, user_id, main_code, token)
        
        if result['success']:
            # ذخیره در دیتابیس
            add_bot(user_id, bot_id, token, bot_name, bot_username, file_path, None, result['pid'])
            total_bots_created += 1
            
            result_text = f"✅ **ربات با موفقیت ساخته و اجرا شد!** 🎉\n\n"
            result_text += f"🤖 نام: {bot_name}\n"
            result_text += f"🔗 لینک: https://t.me/{bot_username}\n"
            result_text += f"🆔 آیدی ربات: `{bot_id}`\n"
            result_text += f"🔄 PID: {result['pid']}\n"
            result_text += f"📦 فایل‌ها: {len(files_content)}\n"
            result_text += f"🔄 وضعیت: در حال اجرا\n\n"
            
            if install_results:
                result_text += f"📚 **کتابخانه‌های نصب شده:**\n"
                for r in install_results:
                    if r['success']:
                        result_text += f"✅ {r['name']}\n"
                    else:
                        result_text += f"❌ {r['name']}: {r['message'][:50]}...\n"
                result_text += "\n"
            
            result_text += f"💡 از /bots برای مشاهده لیست ربات‌ها استفاده کن.\n"
            result_text += f"💡 برای توقف: /stop {bot_id}"
            
            bot.edit_message_text(
                result_text,
                message.chat.id,
                status_msg.message_id,
                parse_mode="Markdown"
            )
        else:
            error_msg = result.get('error', 'خطای ناشناخته')
            bot.edit_message_text(
                f"❌ خطا در اجرای ربات:\n```\n{error_msg}\n```",
                message.chat.id,
                status_msg.message_id,
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.edit_message_text(
            f"❌ خطا: {str(e)}",
            message.chat.id,
            status_msg.message_id
        )

@bot.message_handler(func=lambda m: m.text == '📊 آمار')
def cmd_stats(message):
    global total_requests, total_bots_created, start_time
    
    uptime = datetime.now() - start_time
    hours = uptime.total_seconds() / 3600
    
    with get_db() as conn:
        total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        total_bots = conn.execute('SELECT COUNT(*) FROM bots').fetchone()[0]
        running_bots = conn.execute('SELECT COUNT(*) FROM bots WHERE status = "running"').fetchone()[0]
        pending_receipts = conn.execute('SELECT COUNT(*) FROM receipts WHERE status = "pending"').fetchone()[0]
    
    text = f"📊 **آمار ربات مادر**\n\n"
    text += f"⏱ آپتایم: {hours:.1f} ساعت\n"
    text += f"👥 کاربران: {total_users:,}\n"
    text += f"🤖 ربات‌های ساخته شده: {total_bots:,}\n"
    text += f"🟢 ربات‌های فعال: {running_bots:,}\n"
    text += f"📨 درخواست‌ها: {total_requests:,}\n"
    text += f"⏳ فیش‌های در انتظار: {pending_receipts:,}\n"
    text += f"⚡ وضعیت: 🟢 فعال"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == '📞 پشتیبانی')
def support(message):
    bot.send_message(
        message.chat.id,
        "📞 **پشتیبانی**\n\n"
        "برای ارتباط با پشتیبانی:\n"
        "• @shahraghee13\n"
        "• ۲۴ ساعته پاسخگو هستیم\n\n"
        "🌐 **کانال اعلانات:**\n"
        "@channel"
    )

# ==================== پنل ادمین ====================

@bot.message_handler(func=lambda m: m.text == '👑 پنل ادمین')
def admin_panel(message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ شما دسترسی ادمین ندارید!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📸 مشاهده فیش‌ها", callback_data="admin_receipts"),
        types.InlineKeyboardButton("👥 لیست کاربران", callback_data="admin_users"),
        types.InlineKeyboardButton("🗑 حذف کاربر", callback_data="admin_delete_user"),
        types.InlineKeyboardButton("📊 آمار کامل", callback_data="admin_stats"),
        types.InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")
    )
    
    bot.send_message(
        message.chat.id,
        "👑 **پنل مدیریت**\n\n"
        "یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ دسترسی ندارید!")
        return
    
    msg = bot.send_message(
        call.message.chat.id,
        "📢 **ارسال پیام همگانی**\n\n"
        "متن پیام را وارد کنید:"
    )
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ دسترسی ندارید!")
        return
    
    text = message.text
    
    with get_db() as conn:
        users = conn.execute('SELECT user_id FROM users').fetchall()
    
    sent = 0
    failed = 0
    
    status_msg = bot.reply_to(message, f"🔄 در حال ارسال به {len(users)} کاربر...")
    
    for user in users:
        try:
            bot.send_message(user['user_id'], text)
            sent += 1
        except:
            failed += 1
        
        if sent % 10 == 0:
            bot.edit_message_text(
                f"🔄 پیشرفت: {sent}/{len(users)}",
                message.chat.id,
                status_msg.message_id
            )
    
    bot.edit_message_text(
        f"✅ **ارسال پیام همگانی کامل شد**\n\n"
        f"✅ موفق: {sent}\n"
        f"❌ ناموفق: {failed}\n"
        f"👥 مجموع: {len(users)}",
        message.chat.id,
        status_msg.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_receipts")
def admin_receipts(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ دسترسی ندارید!")
        return
    
    page = 1
    show_receipts_page(call.message, page)

def show_receipts_page(message, page):
    per_page = 5
    offset = (page - 1) * per_page
    
    with get_db() as conn:
        receipts = conn.execute('''
            SELECT * FROM receipts ORDER BY created_at DESC LIMIT ? OFFSET ?
        ''', (per_page, offset)).fetchall()
        
        total = conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]
    
    if not receipts:
        bot.send_message(message.chat.id, "📸 هیچ فیشی وجود ندارد.")
        return
    
    text = f"📸 **فیش‌های واریزی (صفحه {page} از {(total-1)//per_page+1})**\n\n"
    
    for r in receipts:
        status_emoji = "⏳" if r['status'] == 'pending' else "✅" if r['status'] == 'approved' else "❌"
        text += f"{status_emoji} **فیش {r['id']}**\n"
        text += f"👤 کاربر: {r['user_id']}\n"
        text += f"💰 مبلغ: {r['amount']:,} تومان\n"
        text += f"🕐 زمان: {r['created_at'][:16]}\n"
        text += f"📊 وضعیت: {r['status']}\n"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ تایید", callback_data=f"approve_{r['id']}"),
            types.InlineKeyboardButton("❌ رد", callback_data=f"reject_{r['id']}")
        )
        
        # ارسال عکس فیش
        if os.path.exists(r['receipt_path']):
            with open(r['receipt_path'], 'rb') as f:
                bot.send_photo(message.chat.id, f, caption=text, reply_markup=markup)
        else:
            bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_'))
def approve_receipt(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ دسترسی ندارید!")
        return
    
    receipt_id = int(call.data.replace('approve_', ''))
    
    with get_db() as conn:
        receipt = conn.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,)).fetchone()
        if receipt:
            conn.execute('''
                UPDATE receipts SET status = ?, reviewed_at = ?, reviewed_by = ?
                WHERE id = ?
            ''', ('approved', datetime.now().isoformat(), call.from_user.id, receipt_id))
            conn.commit()
            
            # اطلاع به کاربر
            try:
                bot.send_message(
                    receipt['user_id'],
                    f"✅ **فیش واریزی شما تایید شد!**\n\n"
                    f"💰 مبلغ: {receipt['amount']:,} تومان\n"
                    f"اکنون می‌توانید ربات خود را بسازید."
                )
            except:
                pass
    
    bot.answer_callback_query(call.id, "✅ فیش تایید شد")
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_receipt(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ دسترسی ندارید!")
        return
    
    receipt_id = int(call.data.replace('reject_', ''))
    
    with get_db() as conn:
        receipt = conn.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,)).fetchone()
        if receipt:
            conn.execute('''
                UPDATE receipts SET status = ?, reviewed_at = ?, reviewed_by = ?
                WHERE id = ?
            ''', ('rejected', datetime.now().isoformat(), call.from_user.id, receipt_id))
            conn.commit()
            
            # اطلاع به کاربر
            try:
                bot.send_message(
                    receipt['user_id'],
                    f"❌ **فیش واریزی شما رد شد!**\n\n"
                    f"💰 مبلغ: {receipt['amount']:,} تومان\n"
                    f"لطفاً با پشتیبانی تماس بگیرید: @shahraghee13"
                )
            except:
                pass
    
    bot.answer_callback_query(call.id, "❌ فیش رد شد")
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_users")
def admin_users(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ دسترسی ندارید!")
        return
    
    with get_db() as conn:
        users = conn.execute('''
            SELECT user_id, username, first_name, bots_count, verified_referrals, created_at
            FROM users ORDER BY created_at DESC LIMIT 20
        ''').fetchall()
    
    text = "👥 **۲۰ کاربر آخر**\n\n"
    for u in users:
        text += f"🆔 {u['user_id']}\n"
        text += f"👤 {u['first_name']} (@{u['username']})\n"
        text += f"🤖 ربات‌ها: {u['bots_count']} | 🎁 رفرال: {u['verified_referrals']}\n"
        text += f"📅 {u['created_at'][:16]}\n\n"
    
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_user")
def admin_delete_user(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ دسترسی ندارید!")
        return
    
    msg = bot.send_message(
        call.message.chat.id,
        "🗑 **آیدی عددی کاربر را برای حذف وارد کنید:**"
    )
    bot.register_next_step_handler(msg, process_delete_user)

def process_delete_user(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ دسترسی ندارید!")
        return
    
    try:
        user_id = int(message.text)
    except:
        bot.reply_to(message, "❌ آیدی باید عدد باشد!")
        return
    
    with get_db() as conn:
        # حذف ربات‌های کاربر
        bots = conn.execute('SELECT id, pid FROM bots WHERE user_id = ?', (user_id,)).fetchall()
        for b in bots:
            if b['pid']:
                try:
                    bot_engine.stop_bot(b['id'])
                except:
                    pass
        
        # حذف از دیتابیس
        conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM bots WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM receipts WHERE user_id = ?', (user_id,))
        conn.commit()
    
    bot.reply_to(message, f"✅ کاربر {user_id} با تمام ربات‌هایش حذف شد.")

@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def admin_stats(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ دسترسی ندارید!")
        return
    
    with get_db() as conn:
        total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        total_bots = conn.execute('SELECT COUNT(*) FROM bots').fetchone()[0]
        running_bots = conn.execute('SELECT COUNT(*) FROM bots WHERE status = "running"').fetchone()[0]
        total_receipts = conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]
        pending_receipts = conn.execute('SELECT COUNT(*) FROM receipts WHERE status = "pending"').fetchone()[0]
        approved_receipts = conn.execute('SELECT COUNT(*) FROM receipts WHERE status = "approved"').fetchone()[0]
        total_amount = conn.execute('SELECT SUM(amount) FROM receipts WHERE status = "approved"').fetchone()[0] or 0
    
    text = "📊 **آمار کامل سیستم**\n\n"
    text += f"👥 کل کاربران: {total_users:,}\n"
    text += f"🤖 کل ربات‌ها: {total_bots:,}\n"
    text += f"🟢 ربات‌های فعال: {running_bots:,}\n\n"
    text += f"📸 کل فیش‌ها: {total_receipts}\n"
    text += f"⏳ در انتظار: {pending_receipts}\n"
    text += f"✅ تایید شده: {approved_receipts}\n"
    text += f"💰 مجموع واریزی: {total_amount:,} تومان\n"
    
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "admin_back")
def admin_back(call):
    user_id = call.from_user.id
    is_admin = user_id in ADMIN_IDS
    markup = get_main_menu(is_admin)
    
    bot.edit_message_text(
        "🔙 بازگشت به منوی اصلی",
        call.message.chat.id,
        call.message.message_id
    )
    
    bot.send_message(
        call.message.chat.id,
        "🚀 منوی اصلی:",
        reply_markup=markup
    )

# ==================== اجرا ====================
if __name__ == "__main__":
    logger.info("🚀 ربات مادر نهایی با موتور پیشرفته راه‌اندازی شد...")
    logger.info(f"📁 پوشه فایل‌ها: {FILES_DIR}")
    logger.info(f"📁 پوشه ربات‌های در حال اجرا: {RUNNING_DIR}")
    logger.info(f"📁 پوشه فیش‌ها: {RECEIPTS_DIR}")
    logger.info(f"📁 پوشه دیتابیس: {DB_DIR}")
    logger.info(f"📚 تعداد کتابخانه‌های قابل پشتیبانی: {len(library_manager.common_libs)}")
    
    try:
        bot.infinity_polling(timeout=60)
    except Exception as e:
        logger.error(f"خطا: {e}")
        time.sleep(5)
        bot.infinity_polling(timeout=60)
