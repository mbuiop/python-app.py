import asyncio
import logging
from datetime import datetime, timezone
import json
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import re
from web3 import Web3
import requests
from typing import Dict, List, Any, Optional

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
ALCHEMY_API = "39QGDPCD4WNEP1G791ZDPA7WIMX9RR78KI"  # برای تحلیل پیشرفته

# اتصال به Web3
w3_eth = Web3(Web3.HTTPProvider(f"https://eth-mainnet.alchemyapi.io/v2/{ALCHEMY_API}"))
w3_bsc = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org/"))

# آدرس‌های DEX و پروتکل‌های معروف (به‌روزرسانی شده)
PROTOCOL_ADDRESSES = {
    # Uniswap
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": {"name": "Uniswap V2", "type": "DEX"},
    "0xe592427a0aece92de3edee1f18e0157c05861564": {"name": "Uniswap V3", "type": "DEX"},
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": {"name": "Uniswap V3", "type": "DEX"},
    
    # PancakeSwap
    "0x10ed43c718714eb63d5aa57b78b54704e256024e": {"name": "PancakeSwap V2", "type": "DEX"},
    "0x13f4ea83d0bd40e75c8222255bc855a974568dd4": {"name": "PancakeSwap V3", "type": "DEX"},
    
    # GMX (معاملات مارجین)
    "0x489ee077994b6658eafa855c308275ead8097c4a": {"name": "GMX", "type": "PERP"},
    "0xabbc5f99639c9b6bcb58544ddf04efa6802f4064": {"name": "GMX Vault", "type": "PERP"},
    
    # dYdX
    "0x1e0447b19bb6ecfdae1e4ae1694b0c3659614e4e": {"name": "dYdX", "type": "PERP"},
    
    # Compound
    "0x3d9819210a31b4961b30ef54be2aed79b9c9cd3b": {"name": "Compound", "type": "LENDING"},
    
    # Aave
    "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9": {"name": "Aave V2", "type": "LENDING"},
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": {"name": "Aave V3", "type": "LENDING"},
    
    # 1inch
    "0x1111111254eeb25477b68fb85ed929f73a960582": {"name": "1inch", "type": "AGGREGATOR"},
    
    # SushiSwap
    "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f": {"name": "SushiSwap", "type": "DEX"},
    
    # Curve Finance
    "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7": {"name": "Curve Finance", "type": "DEX"},
    
    # Balancer
    "0xba12222222228d8ba445958a75a0704d566bf2c8": {"name": "Balancer", "type": "DEX"},
}

# توکن‌های مهم (به‌روزرسانی شده)
IMPORTANT_TOKENS = {
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
    "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC",
    "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",
    "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "WBNB",
    "0x4d224452801aced8b2f0aebe155379bb5d594381": "APE",
    "0x7d1afa7b718fb893db30a3abc0cfc608aacfebb0": "MATIC",
}

# ABIهای لازم برای تحلیل پیشرفته
UNISWAP_V2_ABI = [
    {
        "name": "swap",
        "type": "function",
        "inputs": [
            {"type": "uint256", "name": "amount0Out"},
            {"type": "uint256", "name": "amount1Out"},
            {"type": "address", "name": "to"},
            {"type": "bytes", "name": "data"}
        ]
    }
]

UNISWAP_V3_ABI = [
    {
        "name": "exactInputSingle",
        "type": "function",
        "inputs": [
            {"type": "tuple", "name": "params", "components": [
                {"type": "address", "name": "tokenIn"},
                {"type": "address", "name": "tokenOut"},
                {"type": "uint24", "name": "fee"},
                {"type": "address", "name": "recipient"},
                {"type": "uint256", "name": "deadline"},
                {"type": "uint256", "name": "amountIn"},
                {"type": "uint256", "name": "amountOutMinimum"},
                {"type": "uint160", "name": "sqrtPriceLimitX96"}
            ]}
        ]
    }
]

GMX_ABI = [
    {
        "name": "createIncreasePosition",
        "type": "function",
        "inputs": [
            {"type": "address[]", "name": "_path"},
            {"type": "address", "name": "_indexToken"},
            {"type": "uint256", "name": "_amountIn"},
            {"type": "uint256", "name": "_minOut"},
            {"type": "uint256", "name": "_sizeDelta"},
            {"type": "bool", "name": "_isLong"},
            {"type": "uint256", "name": "_acceptablePrice"},
            {"type": "uint256", "name": "_executionFee"},
            {"type": "bytes32", "name": "_referralCode"},
            {"type": "address", "name": "_callbackTarget"}
        ]
    }
]

class AdvancedWhaleTracker:
    def __init__(self):
        self.session = None
        self.price_cache = {}
    
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def get_token_price(self, token_address: str, network: str = "eth") -> float:
        """دریافت قیمت توکن از CoinGecko"""
        if token_address in self.price_cache:
            return self.price_cache[token_address]
        
        try:
            # تبدیل آدرس به نماد برای CoinGecko
            symbol = IMPORTANT_TOKENS.get(token_address.lower(), "")
            if not symbol:
                return 0.0
            
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = data.get(symbol.lower(), {}).get("usd", 0.0)
                        self.price_cache[token_address] = price
                        return price
        except Exception as e:
            logger.error(f"خطا در دریافت قیمت: {e}")
        
        return 0.0
    
    async def get_wallet_transactions(self, address: str, network: str = "eth", limit: int = 100) -> List[Dict]:
        """دریافت تراکنش‌های کیف پول با جزئیات کامل"""
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
                    transactions = data.get("result", [])
                    
                    # دریافت تراکنش‌های داخلی
                    internal_params = {
                        "module": "account",
                        "action": "txlistinternal",
                        "address": address,
                        "startblock": 0,
                        "endblock": 99999999,
                        "page": 1,
                        "offset": 50,
                        "sort": "desc",
                        "apikey": api_key
                    }
                    
                    async with session.get(base_url, params=internal_params) as internal_response:
                        if internal_response.status == 200:
                            internal_data = await internal_response.json()
                            internal_txs = internal_data.get("result", [])
                            # ادغام تراکنش‌ها
                            transactions.extend(internal_txs)
                    
                    return transactions
            
            return []
        except Exception as e:
            logger.error(f"خطا در دریافت تراکنش‌ها: {e}")
            return []
    
    async def analyze_transaction_advanced(self, tx: Dict, network: str = "eth") -> Optional[Dict]:
        """تجزیه و تحلیل پیشرفته تراکنش"""
        try:
            to_address = tx.get("to", "").lower()
            from_address = tx.get("from", "").lower()
            value = int(tx.get("value", "0"))
            gas_used = int(tx.get("gasUsed", "0"))
            gas_price = int(tx.get("gasPrice", "0"))
            
            # محاسبه هزینه گس
            gas_cost = (gas_used * gas_price) / 1e18
            
            # چک کردن آیا به پروتکل شناخته شده است
            protocol_info = PROTOCOL_ADDRESSES.get(to_address)
            if not protocol_info:
                # چک کردن contract creation
                if not to_address and tx.get("input", "").startswith("0x"):
                    return {
                        "hash": tx.get("hash"),
                        "timestamp": datetime.fromtimestamp(int(tx.get("timeStamp", "0"))),
                        "type": "CONTRACT_CREATION",
                        "value": value / 1e18,
                        "gas_used": gas_used,
                        "gas_cost": gas_cost,
                        "explorer_url": f"https://etherscan.io/tx/{tx.get('hash')}" if network == "eth" else f"https://bscscan.com/tx/{tx.get('hash')}",
                        "analysis": {"action": "Contract Deployment", "description": "ایجاد قرارداد جدید"}
                    }
                return None
            
            # تجزیه و تحلیل پیشرفته Input Data
            input_data = tx.get("input", "")
            analysis = await self.advanced_analyze_input_data(input_data, protocol_info, tx, network)
            
            if not analysis:
                return None
            
            result = {
                "hash": tx.get("hash"),
                "timestamp": datetime.fromtimestamp(int(tx.get("timeStamp", "0"))),
                "protocol": protocol_info["name"],
                "protocol_type": protocol_info["type"],
                "value": value / 1e18,
                "gas_used": gas_used,
                "gas_cost": gas_cost,
                "analysis": analysis,
                "explorer_url": f"https://etherscan.io/tx/{tx.get('hash')}" if network == "eth" else f"https://bscscan.com/tx/{tx.get('hash')}"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"خطا در تجزیه و تحلیل تراکنش: {e}")
            return None
    
    async def advanced_analyze_input_data(self, input_data: str, protocol_info: Dict, tx: Dict, network: str) -> Dict:
        """تجزیه و تحلیل پیشرفته داده‌های ورودی"""
        if not input_data or input_data == "0x":
            return {"type": "simple_transfer", "action": "Transfer", "description": "انتقال ساده"}
        
        method_id = input_data[:10]
        w3 = w3_eth if network == "eth" else w3_bsc
        
        try:
            # تحلیل بر اساس نوع پروتکل
            if protocol_info["type"] == "DEX":
                return await self.analyze_dex_trade(method_id, input_data, protocol_info, w3)
            elif protocol_info["type"] == "PERP":
                return await self.analyze_perp_trade(method_id, input_data, protocol_info, w3, tx)
            elif protocol_info["type"] == "LENDING":
                return await self.analyze_lending_trade(method_id, input_data, protocol_info, w3)
            else:
                return self.identify_trade_type(method_id, protocol_info)
        except Exception as e:
            logger.error(f"خطا در تحلیل پیشرفته: {e}")
            return self.identify_trade_type(method_id, protocol_info)
    
    async def analyze_dex_trade(self, method_id: str, input_data: str, protocol_info: Dict, w3) -> Dict:
        """تحلیل معاملات DEX"""
        base_analysis = self.identify_trade_type(method_id, protocol_info)
        
        try:
            # decode کردن داده‌ها
            if method_id == "0x7ff36ab5":  # swapExactETHForTokens
                decoded = w3.eth.contract(abi=UNISWAP_V2_ABI).decode_function_input(input_data)
                amount_out_min = decoded[1]["amountOutMin"]
                path = decoded[1]["path"]
                
                base_analysis.update({
                    "amount_out_min": amount_out_min,
                    "path_length": len(path),
                    "token_path": [IMPORTANT_TOKENS.get(addr.lower(), addr) for addr in path],
                    "trade_size_usd": await self.estimate_trade_size(decoded[1]["amountIn"], "ETH")
                })
                
            elif method_id == "0x38ed1739":  # swapExactTokensForTokens
                decoded = w3.eth.contract(abi=UNISWAP_V2_ABI).decode_function_input(input_data)
                base_analysis.update({
                    "amount_in": decoded[1]["amountIn"],
                    "amount_out_min": decoded[1]["amountOutMin"],
                    "path_length": len(decoded[1]["path"]),
                    "trade_size_usd": await self.estimate_trade_size(decoded[1]["amountIn"], decoded[1]["path"][0])
                })
            
        except Exception as e:
            logger.error(f"خطا در تحلیل DEX: {e}")
        
        return base_analysis
    
    async def analyze_perp_trade(self, method_id: str, input_data: str, protocol_info: Dict, w3, tx: Dict) -> Dict:
        """تحلیل معاملات پرپچوال"""
        base_analysis = self.identify_trade_type(method_id, protocol_info)
        
        try:
            if "createIncreasePosition" in base_analysis["description"]:
                decoded = w3.eth.contract(abi=GMX_ABI).decode_function_input(input_data)
                
                size_delta = decoded[1]["_sizeDelta"] / 1e30  # تبدیل به واحد قابل خواندن
                amount_in = decoded[1]["_amountIn"] / 1e18
                
                # محاسبه اهرم
                leverage = size_delta / amount_in if amount_in > 0 else 0
                
                base_analysis.update({
                    "position_type": "LONG" if decoded[1]["_isLong"] else "SHORT",
                    "size_delta": size_delta,
                    "                })
                
        except Exception as e:
            logger.error(f"خطا در تحلیل پرپچوال: {e}")
        
        return base_analysis
    
    async def analyze_lending_trade(self, method_id: str, input_data: str, protocol_info: Dict, w3) -> Dict:
        """تحلیل معاملات لندینگ"""
        return self.identify_trade_type(method_id, protocol_info)
    
    def identify_trade_type(self, method_id: str, protocol_info: Dict) -> Dict:
        """شناسایی نوع معامله بر اساس method_id"""
        method_map = {
            # Uniswap/PancakeSwap
            "0x7ff36ab5": {"action": "BUY", "description": "خرید توکن با ETH/BNB"},
            "0x18cbafe5": {"action": "SELL", "description": "فروش توکن برای ETH/BNB"},
            "0x38ed1739": {"action": "SWAP", "description": "سوآپ توکن‌ها"},
            
            # GMX
            "0x1e6f5c3a": {"action": "LONG/SHORT", "description": "ایجاد پوزیشن لانگ/شورت"},
            "0x601e1261": {"action": "CLOSE", "description": "بستن پوزیشن"},
            
            # Aave/Compound
            "0xe8eda9df": {"action": "DEPOSIT", "description": "واریز به استخر لندینگ"},
            "0x69328dec": {"action": "WITHDRAW", "description": "برداشت از استخر لندینگ"},
            "0x573ade81": {"action": "BORROW", "description": "قرض گرفتن"},
            "0x0e752702": {"action": "REPAY", "description": "بازپرداخت وام"},
        }
        
        return method_map.get(method_id, {
            "action": "UNKNOWN",
            "description": f"معامله در {protocol_info['name']}",
            "method_id": method_id
        })
    
    async def estimate_trade_size(self, amount: int, token_address: str) -> float:
        """تخمین حجم معامله به دلار"""
        try:
            if token_address == "ETH":
                eth_price = await self.get_token_price("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")
                return (amount / 1e18) * eth_price
            
            token_price = await self.get_token_price(token_address)
            return (amount / 1e18) * token_price
        except:
            return 0.0
    
    def get_leverage_level(self, leverage: float) -> str:
        """تعیین سطح اهرم"""
        if leverage <= 2:
            return "LOW"
        elif leverage <= 5:
            return "MEDIUM"
        elif leverage <= 10:
            return "HIGH"
        else:
            return "EXTREME"

# ایجاد نمونه ردیاب
tracker = AdvancedWhaleTracker()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور شروع"""
    welcome_text = """
    🐋 **ربات ردیاب نهنگ‌های کریپتو - نسخه سنگین** 🐋

    این ربات با قابلیت‌های فوق پیشرفته:
    • 🔍 ردیابی دقیق معاملات نهنگ‌ها
    • 📊 تحلیل لانگ/شورت و اهرم
    • ⚡ شناسایی نقطه ورود و خروج
    • 💰 محاسبه حجم معاملات به دلار
    • 🚨 هشدار معاملات بزرگ

    برای شروع، آدرس والت را ارسال کنید:
    `/track 0x...` - ردیابی آدرس
    `/analyze 0x...` - تحلیل کامل
    """
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def track_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ردیابی کیف پول"""
    if not context.args:
        await update.message.reply_text("لطفاً آدرس والت را وارد کنید: `/track 0x...`")
        return
    
    address = context.args[0].lower()
    
    if not re.match(r"^0x[a-fA-F0-9]{40}$", address):
        await update.message.reply_text("آدرس نامعتبر است!")
        return
    
    # ارسال پیام در حال پردازش
    processing_msg = await update.message.reply_text("🔍 در حال تحلیل سنگین معاملات...")
    
    try:
        # دریافت و تحلیل تراکنش‌ها
        transactions = await tracker.get_wallet_transactions(address, "eth", 50)
        
        if not transactions:
            await processing_msg.edit_text("هیچ تراکنشی یافت نشد!")
            return
        
        # تحلیل 10 تراکنش آخر
        analyzed_txs = []
        for tx in transactions[:10]:
            analysis = await tracker.analyze_transaction_advanced(tx, "eth")
            if analysis:
                analyzed_txs.append(analysis)
        
        if not analyzed_txs:
            await processing_msg.edit_text("هیچ معامله قابل تحلیلی یافت نشد!")
            return
        
        # ایجاد گزارش
        report = await generate_detailed_report(analyzed_txs, address)
        await processing_msg.edit_text(report, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"خطا در ردیابی: {e}")
        await processing_msg.edit_text("خطا در پردازش!")

async def analyze_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحلیل کامل کیف پول"""
    if not context.args:
        await update.message.reply_text("لطفاً آدرس والت را وارد کنید: `/analyze 0x...`")
        return
    
    address = context.args[0].lower()
    
    if not re.match(r"^0x[a-fA-F0-9]{40}$", address):
        await update.message.reply_text("آدرس نامعتبر است!")
        return
    
    # ارسال پیام در حال پردازش
    processing_msg = await update.message.reply_text("⚡ در حال تحلیل فوق سنگین...")
    
    try:
        # دریافت تراکنش‌ها
        transactions = await tracker.get_wallet_transactions(address, "eth", 100)
        
        if not transactions:
            await processing_msg.edit_text("هیچ تراکنشی یافت نشد!")
            return
        
        # تحلیل کامل
        analyzed_txs = []
        for tx in transactions:
            analysis = await tracker.analyze_transaction_advanced(tx, "eth")
            if analysis:
                analyzed_txs.append(analysis)
        
        if not analyzed_txs:
            await processing_msg.edit_text("هیچ معامله قابل تحلیلی یافت نشد!")
            return
        
        # ایجاد گزارش کامل
        full_report = await generate_comprehensive_report(analyzed_txs, address)
        
        # ارسال گزارش به صورت فایل برای خوانایی بهتر
        filename = f"analysis_{address[:8]}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(full_report)
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=open(filename, "rb"),
            caption=f"📊 گزارش کامل تحلیل والت: `{address}`"
        )
        
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"خطا در تحلیل: {e}")
        await processing_msg.edit_text("خطا در پردازش!")

async def generate_detailed_report(transactions: List[Dict], address: str) -> str:
    """ایجاد گزارش دقیق"""
    report = f"📊 **گزارش تحلیل والت: ** `{address}`\n\n"
    report += f"📈 **تعداد معاملات تحلیل شده:** {len(transactions)}\n\n"
    
    for i, tx in enumerate(transactions, 1):
        analysis = tx["analysis"]
        
        report += f"**{i}. 🎯 معامله در {tx['protocol']}**\n"
        report += f"   ⏰ زمان: {tx['timestamp'].strftime('%Y-%m-%d %H:%M')}\n"
        report += f"   🔧 نوع: {analysis.get('action', 'UNKNOWN')}\n"
        report += f"   📝 توضیحات: {analysis.get('description', '')}\n"
        
        if "position_type" in analysis:
            report += f"   📊 پوزیشن: {analysis['position_type']}\n"
        if "leverage" in analysis:
            report += f"   ⚖️ اهرم: {analysis['leverage']}x ({analysis.get('leverage_level', '')})\n"
        if "trade_size_usd" in analysis and analysis["trade_size_usd"] > 0:
            report += f"   💰 حجم: ${analysis['trade_size_usd']:,.2f}\n"
        
        report += f"   ⛽ گس: {tx['gas_used']:,} (${tx['gas_cost']:.4f})\n"
        report += f"   🔗 [مشاهده تراکنش]({tx['explorer_url']})\n\n"
    
    return report

async def generate_comprehensive_report(transactions: List[Dict], address: str) -> str:
    """ایجاد گزارش جامع"""
    # محاسبات آماری
    total_gas = sum(tx["gas_cost"] for tx in transactions)
    total_volume = sum(tx["analysis"].get("trade_size_usd", 0) for tx in transactions 
                      if "trade_size_usd" in tx["analysis"])
    
    # تحلیل فعالیت
    protocol_counts = {}
    position_types = {"LONG": 0, "SHORT": 0}
    
    for tx in transactions:
        protocol = tx["protocol"]
        protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1
        
        if tx["analysis"].get("position_type"):
            position_types[tx["analysis"]["position_type"]] += 1
    
    # ایجاد گزارش
    report = "=" * 60 + "\n"
    report += "🐋 گزارش تحلیل جامع نهنگ 🐋\n"
    report += "=" * 60 + "\n\n"
    
    report += f"آدرس: {address}\n"
    report += f"تاریخ تحلیل: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    report += f"تعداد معاملات تحلیل شده: {len(transactions)}\n\n"
    
    report += "📈 آمار کلی:\n"
    report += f"• حجم کل معاملات: ${total_volume:,.2f}\n"
    report += f"• هزینه کل گس: ${total_gas:.4f}\n"
    report += f"• میانگین حجم معامله: ${total_volume/len(transactions):,.2f}\n\n"
    
    report += "🏦 فعالیت در پروتکل‌ها:\n"
    for protocol, count in sorted(protocol_counts.items(), key=lambda x: x[1], reverse=True):
        report += f"• {protocol}: {count} معامله\n"
    
    if any(position_types.values()):
        report += "\n📊 پوزیشن‌های معاملاتی:\n"
        report += f"• لانگ: {position_types['LONG']}\n"
        report += f"• شورت: {position_types['SHORT']}\n"
    
    report += "\n" + "=" * 60 + "\n"
    report += "🧠 تحلیل رفتاری:\n"
    
    # تحلیل رفتار معاملاتی
    if position_types.get("LONG", 0) > position_types.get("SHORT", 0):
        report += "• تمایل به پوزیشن‌های لانگ (صعودی)\n"
    elif position_types.get("SHORT", 0) > position_types.get("LONG", 0):
        report += "• تمایل به پوزیشن‌های شورت (نزولی)\n"
    
    if total_volume > 1000000:  # بیش از 1M
        report += "• نهنگ سنگین وزن (حجم معاملات بالا)\n"
    elif total_volume > 100000:  # بیش از 100K
        report += "• نهنگ متوسط\n"
    else:
        report += "• نهنگ کوچک\n"
    
    report += "\n" + "=" * 60 + "\n"
    report += "📋 جزئیات معاملات:\n\n"
    
    for i, tx in enumerate(transactions, 1):
        analysis = tx["analysis"]
        
        report += f"{i}. {tx['timestamp'].strftime('%Y-%m-%d %H:%M')} - {tx['protocol']}\n"
        report += f"   نوع: {analysis.get('action', 'UNKNOWN')} - {analysis.get('description', '')}\n"
        
        if "trade_size_usd" in analysis:
            report += f"   حجم: ${analysis['trade_size_usd']:,.2f}\n"
        if "leverage" in analysis:
            report += f"   اهرم: {analysis['leverage']}x\n"
        
        report += f"   گس: {tx['gas_used']:,} (${tx['gas_cost']:.4f})\n"
        report += f"   لینک: {tx['explorer_url']}\n\n"
    
    return report

def main():
    """تابع اصلی"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن handlerها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("track", track_wallet))
    application.add_handler(CommandHandler("analyze", analyze_wallet))
    
    # شروع بات
    application.run_polling()

if __name__ == "__main__":
    main()
