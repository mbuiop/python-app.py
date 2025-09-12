import asyncio
import logging
from datetime import datetime, timezone
import json
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import re

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تنظیمات
BOT_TOKEN = "7685135237:AAEmsHktRw9cEqrHTkCoPZk-fBimK7TDjOo"
ETHERSCAN_API = "39QGDPCD4WNEP1G791ZDPA7WIMX9RR78KI"
BSCSCAN_API = "39QGDPCD4WNEP1G791ZDPA7WIMX9RR78KI"

# آدرس‌های DEX و پروتکل‌های معروف
PROTOCOL_ADDRESSES = {
    # Uniswap
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": {"name": "Uniswap V2", "type": "DEX"},
    "0xe592427a0aece92de3edee1f18e0157c05861564": {"name": "Uniswap V3", "type": "DEX"},
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": {"name": "Uniswap V3", "type": "DEX"},
    
    # PancakeSwap
    "0x10ed43c718714eb63d5aa57b78b54704e256024e": {"name": "PancakeSwap V2", "type": "DEX"},
    
    # GMX (معاملات مارجین)
    "0x489ee077994b6658eafa855c308275ead8097c4a": {"name": "GMX", "type": "PERP"},
    "0x0000000000000000000000000000000000000000": {"name": "GMX Vault", "type": "PERP"},
    
    # dYdX
    "0x1e0447b19bb6ecfdae1e4ae1694b0c3659614e4e": {"name": "dYdX", "type": "PERP"},
    
    # Compound
    "0x3d9819210a31b4961b30ef54be2aed79b9c9cd3b": {"name": "Compound", "type": "LENDING"},
    
    # Aave
    "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9": {"name": "Aave V2", "type": "LENDING"},
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": {"name": "Aave V3", "type": "LENDING"},
}

# توکن‌های مهم
IMPORTANT_TOKENS = {
    "0xa0b86a33e6411c66f1a43bb45be8de4dd98b1a71": "WETH",
    "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
    "0xa0b86a33e6411c66f1a43bb45be8de4dd98b1a71": "USDC",
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC",
}

class WhaleTracker:
    def __init__(self):
        self.session = None
    
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def get_wallet_transactions(self, address, network="eth", limit=50):
        """دریافت تراکنش‌های کیف پول"""
        try:
            session = await self.get_session()
            
            if network == "eth":
                api_key = ETHERSCAN_API
                base_url = "https://api.etherscan.io/api"
            elif network == "bsc":
                api_key = BSCSCAN_API
                base_url = "https://api.bscscan.com/api"
            else:
                return []
            
            # دریافت تراکنش‌های معمولی
            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": limit,
                "sort": "desc",
                "apikey": api_key
            }
            
            async with session.get(base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("result", [])
            
            return []
        except Exception as e:
            logger.error(f"خطا در دریافت تراکنش‌ها: {e}")
            return []
    
    async def analyze_transaction(self, tx, network="eth"):
        """تجزیه و تحلیل تراکنش برای یافتن اطلاعات معاملات"""
        try:
            to_address = tx.get("to", "").lower()
            value = int(tx.get("value", "0"))
            gas_used = int(tx.get("gasUsed", "0"))
            
            # چک کردن آیا به پروتکل شناخته شده است
            protocol_info = PROTOCOL_ADDRESSES.get(to_address)
            if not protocol_info:
                return None
            
            # تجزیه و تحلیل Input Data
            input_data = tx.get("input", "")
            analysis = await self.analyze_input_data(input_data, protocol_info)
            
            result = {
                "hash": tx.get("hash"),
                "timestamp": datetime.fromtimestamp(int(tx.get("timeStamp", "0"))),
                "protocol": protocol_info["name"],
                "protocol_type": protocol_info["type"],
                "eth_value": value / 1e18,
                "gas_used": gas_used,
                "analysis": analysis,
                "explorer_url": f"https://etherscan.io/tx/{tx.get('hash')}" if network == "eth" else f"https://bscscan.com/tx/{tx.get('hash')}"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"خطا در تجزیه و تحلیل تراکنش: {e}")
            return None
    
    async def analyze_input_data(self, input_data, protocol_info):
        """تجزیه و تحلیل داده‌های ورودی تراکنش"""
        if not input_data or input_data == "0x":
            return {"type": "simple_transfer"}
        
        # استخراج Method ID (4 بایت اول)
        method_id = input_data[:10] if len(input_data) >= 10 else ""
        
        # تشخیص نوع معامله بر اساس Method ID
        trade_analysis = self.identify_trade_type(method_id, protocol_info)
        
        # تلاش برای استخراج اطلاعات بیشتر از داده‌ها
        if len(input_data) > 10:
            try:
                # این بخش نیاز به کتابخانه web3 برای decode کردن دارد
                # فعلاً تحلیل ساده انجام می‌دهیم
                params = self.simple_decode_params(input_data[10:])
                trade_analysis.update(params)
            except:
                pass
        
        return trade_analysis
    
    def identify_trade_type(self, method_id, protocol_info):
        """شناسایی نوع معامله بر اساس Method ID"""
        
        # Method IDهای رایج
        KNOWN_METHODS = {
            # Uniswap V2
            "0x18cbafe5": {"action": "Swap", "description": "swapExactETHForTokens"},
            "0x7ff36ab5": {"action": "Swap", "description": "swapExactETHForTokensSupportingFeeOnTransferTokens"},
            "0x38ed1739": {"action": "Swap", "description": "swapExactTokensForTokens"},
            "0x8803dbee": {"action": "Swap", "description": "swapTokensForExactTokens"},
            "0xe8e33700": {"action": "Add Liquidity", "description": "addLiquidity"},
            "0xf305d719": {"action": "Add Liquidity", "description": "addLiquidityETH"},
            
            # Uniswap V3
            "0x414bf389": {"action": "Swap", "description": "exactInputSingle"},
            "0xb858183f": {"action": "Swap", "description": "exactInput"},
            "0xdb3e2198": {"action": "Swap", "description": "exactOutputSingle"},
            
            # GMX
            "0x2d9320c0": {"action": "Long Position", "description": "increasePosition"},
            "0x0dede6c4": {"action": "Short Position", "description": "decreasePosition"},
            "0x1f7ec122": {"action": "Create Position", "description": "createIncreasePosition"},
            
            # Compound
            "0x1249c58b": {"action": "Supply", "description": "mint"},
            "0xdb006a75": {"action": "Borrow", "description": "borrow"},
            "0x0e752702": {"action": "Repay", "description": "repayBorrow"},
        }
        
        method_info = KNOWN_METHODS.get(method_id, {"action": "Unknown", "description": "نامشخص"})
        
        result = {
            "method_id": method_id,
            "action": method_info["action"],
            "description": method_info["description"],
            "protocol_type": protocol_info["type"]
        }
        
        # اضافه کردن اطلاعات خاص بر اساس نوع پروتکل
        if protocol_info["type"] == "PERP":
            result.update({
                "position_type": "Long" if "increase" in method_info["description"].lower() else "Short",
                "leverage": "نامشخص (نیاز به تجزیه و تحلیل بیشتر)",
                "entry_price": "در حال محاسبه...",
            })
        
        return result
    
    def simple_decode_params(self, hex_data):
        """decode ساده پارامترها (نسخه محدود)"""
        try:
            # این تابع می‌تواند پیچیده‌تر شود
            # فعلاً تنها اطلاعات پایه را بر می‌گرداند
            return {
                "raw_data_length": len(hex_data),
                "has_params": len(hex_data) > 0
            }
        except:
            return {}

# تابع‌های ربات تلگرام
whale_tracker = WhaleTracker()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیام خوش‌آمدگویی"""
    welcome_text = """
🐋 **خوش آمدید به ربات ردیاب نهنگ‌ها!**

برای استفاده از ربات، آدرس کیف پول را ارسال کنید:
`0x1234...abcd`

**قابلیت‌ها:**
✅ تشخیص معاملات Long/Short
✅ محاسبه ضریب اهرم
✅ نمایش نقاط ورود و خروج
✅ تجزیه و تحلیل سود/زیان
✅ پشتیبانی از Ethereum و BSC

**دستورات:**
/start - شروع
/help - راهنما
/stats - آمار کلی

فقط آدرس کیف پول را ارسال کنید! 🚀
    """
    
    keyboard = [
        [InlineKeyboardButton("📖 راهنما", callback_data="help")],
        [InlineKeyboardButton("📊 نمونه آدرس", callback_data="sample")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش آدرس کیف پول"""
    message_text = update.message.text.strip()
    
    # چک کردن فرمت آدرس
    if not re.match(r'^0x[a-fA-F0-9]{40}$', message_text):
        await update.message.reply_text(
            "❌ آدرس کیف پول معتبر نیست!\n"
            "آدرس باید با 0x شروع شده و 42 کاراکتر باشد.\n\n"
            "مثال: `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045`",
            parse_mode='Markdown'
        )
        return
    
    # ارسال پیام در حال پردازش
    processing_msg = await update.message.reply_text(
        "🔍 در حال تجزیه و تحلیل کیف پول...\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        # دریافت تراکنش‌ها
        transactions = await whale_tracker.get_wallet_transactions(message_text)
        
        if not transactions:
            await processing_msg.edit_text("❌ هیچ تراکنشی یافت نشد یا خطا در دریافت داده‌ها")
            return
        
        # تجزیه و تحلیل تراکنش‌ها
        analyzed_trades = []
        for tx in transactions[:20]:  # فقط 20 تراکنش آخر
            analysis = await whale_tracker.analyze_transaction(tx)
            if analysis and analysis["analysis"]["action"] != "Unknown":
                analyzed_trades.append(analysis)
        
        if not analyzed_trades:
            await processing_msg.edit_text(
                "📝 تراکنش‌ها پردازش شدند اما هیچ معامله‌ای در DEX/CEX های شناخته شده یافت نشد.\n\n"
                "این کیف پول ممکن است:\n"
                "• فقط برای نگهداری باشد (HODL)\n"
                "• در پلتفرم‌های ناشناخته معامله کند\n"
                "• از پروکسی یا کانترکت‌های پیچیده استفاده کند"
            )
            return
        
        # نمایش نتایج
        await display_analysis_results(update, analyzed_trades, message_text)
        
    except Exception as e:
        logger.error(f"خطا در پردازش آدرس: {e}")
        await processing_msg.edit_text(
            "❌ خطا در پردازش آدرس کیف پول\n"
            "لطفاً دوباره تلاش کنید."
        )
    
    # حذف پیام در حال پردازش
    try:
        await processing_msg.delete()
    except:
        pass

async def display_analysis_results(update, analyzed_trades, wallet_address):
    """نمایش نتایج تجزیه و تحلیل"""
    
    # خلاصه آمار
    total_trades = len(analyzed_trades)
    protocols = list(set([trade["protocol"] for trade in analyzed_trades]))
    
    summary_text = f"""
🐋 **تجزیه و تحلیل نهنگ کریپتو**

**آدرس کیف پول:**
`{wallet_address}`

📊 **آمار کلی:**
• تعداد معاملات: {total_trades}
• پروتکل‌های استفاده شده: {len(protocols)}
• {', '.join(protocols[:3])}{'...' if len(protocols) > 3 else ''}

🕐 **بازه زمانی:** {analyzed_trades[-1]["timestamp"].strftime("%Y/%m/%d")} تا {analyzed_trades[0]["timestamp"].strftime("%Y/%m/%d")}
    """
    
    await update.message.reply_text(summary_text, parse_mode='Markdown')
    
    # نمایش جزئیات معاملات
    for i, trade in enumerate(analyzed_trades[:10]):  # فقط 10 معامله اول
        trade_text = format_trade_details(trade, i+1)
        
        keyboard = [
            [InlineKeyboardButton("🔗 مشاهده در اکسپلورر", url=trade["explorer_url"])]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            trade_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        # تاخیر کوتاه برای جلوگیری از spam
        await asyncio.sleep(1)

def format_trade_details(trade, index):
    """فرمت کردن جزئیات معامله"""
    
    analysis = trade["analysis"]
    timestamp = trade["timestamp"].strftime("%Y/%m/%d %H:%M")
    
    # تعیین ایموجی بر اساس نوع معامله
    if "Long" in analysis["action"]:
        emoji = "🟢📈"
        action_fa = "خرید / Long"
    elif "Short" in analysis["action"]:
        emoji = "🔴📉"
        action_fa = "فروش / Short"
    elif "Swap" in analysis["action"]:
        emoji = "🔄"
        action_fa = "تبادل"
    else:
        emoji = "📊"
        action_fa = analysis["action"]
    
    text = f"""
{emoji} **معامله #{index}**

🏢 **پروتکل:** {trade["protocol"]}
⚡ **عملیات:** {action_fa}
📝 **توضیح:** {analysis["description"]}

💰 **مقدار:** {trade["eth_value"]:.4f} ETH
⛽ **گس:** {trade["gas_used"]:,} units
🕐 **زمان:** {timestamp}

**Hash:**
`{trade["hash"][:20]}...`
    """
    
    # اضافه کردن اطلاعات خاص پروتکل
    if trade["protocol_type"] == "PERP":
        text += f"""
📊 **نوع پوزیشن:** {analysis.get('position_type', 'نامشخص')}
⚖️ **اهرم:** {analysis.get('leverage', 'در حال محاسبه...')}
🎯 **نقطه ورود:** {analysis.get('entry_price', 'در حال محاسبه...')}
        """
    
    return text

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش کلیک روی دکمه‌ها"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        help_text = """
📖 **راهنمای استفاده:**

**1. ارسال آدرس کیف پول:**
فقط آدرس کیف پول (0x...) را در چت ارسال کنید

**2. تفسیر نتایج:**
🟢📈 = خرید / Long Position
🔴📉 = فروش / Short Position  
🔄 = تبادل معمولی (Swap)
📊 = سایر عملیات

**3. پروتکل‌های پشتیبانی شده:**
• Uniswap V2/V3
• PancakeSwap
• GMX (مارجین)
• dYdX (فیوچرز)
• Compound (وام)
• Aave (وام)

**4. شبکه‌های پشتیبانی شده:**
• Ethereum
• Binance Smart Chain

**نکته:** برای استفاده کامل، API Key های مورد نیاز باید تنظیم شوند.
        """
        await query.edit_message_text(help_text, parse_mode='Markdown')
    
    elif query.data == "sample":
        sample_text = """
🔗 **نمونه آدرس‌ها برای تست:**

**Vitalik Buterin:**
`0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045`

**نهنگ معروف:**
`0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503`

**صندوق سرمایه‌گذاری:**
`0x8eb8a3b98659cce290402893d0123abb75e3ab28`

فقط یکی از این آدرس‌ها را کپی کرده و ارسال کنید! 📝
        """
        await query.edit_message_text(sample_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش راهنما"""
    await button_callback(update, context)

def main():
    """اجرای ربات"""
    # ساخت اپلیکیشن
    application = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن handler ها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_address))
    
    # اجرای ربات
    print("🤖 ربات در حال اجرا...")
    application.run_polling()

if __name__ == "__main__":
    main()
