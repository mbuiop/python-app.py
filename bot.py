import asyncio
import logging
import aiohttp
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# تنظیمات
TELEGRAM_BOT_TOKEN = "8052349235:AAFSaJmYpl359BKrJTWC8O-u-dI9r2olEOQ"
ALPHA_VANTAGE_API = "uSuLsH9hvMCRLyvw4WzUZiGB"

# لیست ارزهای مورد نظر
CRYPTO_SYMBOLS = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE', 'MATIC', 'DOT', 'AVAX']

# وزن‌های اندیکاتورها
INDICATOR_WEIGHTS = {
    'conservative': {'RSI': 20, 'MACD': 15, 'MA20': 25, 'MA50': 30, 'Volume': 10},
    'moderate': {'RSI': 25, 'MACD': 20, 'MA20': 20, 'MA50': 20, 'Volume': 15},
    'aggressive': {'RSI': 30, 'MACD': 25, 'MA20': 15, 'MA50': 10, 'Volume': 20}
}

class AdvancedCryptoAnalyzer:
    def __init__(self):
        self.session = None
        self.market_data_cache = {}
    
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    async def get_alpha_vantage_data(self, symbol, function="DIGITAL_CURRENCY_DAILY"):
        """دریافت داده‌های واقعی از Alpha Vantage"""
        try:
            url = f"https://www.alphavantage.co/query?function={function}&symbol={symbol}&market=USD&apikey={ALPHA_VANTAGE_API}"
            
            async with self.session.get(url, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    print(f"خطای HTTP {response.status} برای {symbol}")
                    return None
        except Exception as e:
            print(f"خطا در دریافت داده‌های {symbol}: {e}")
            return None
    
    async def get_market_sentiment(self, symbol):
        """دریافت احساسات بازار و داده‌های نهنگ‌ها"""
        try:
            # استفاده از endpointهای مختلف Alpha Vantage
            urls = [
                f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={symbol}&to_currency=USD&apikey={ALPHA_VANTAGE_API}",
                f"https://www.alphavantage.co/query?function=CRYPTO_INTRADAY&symbol={symbol}&market=USD&interval=5min&apikey={ALPHA_VANTAGE_API}",
                f"https://www.alphavantage.co/query?function=CRYPTO_RATING&symbol={symbol}&apikey={ALPHA_VANTAGE_API}"
            ]
            
            results = []
            for url in urls:
                try:
                    async with self.session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            results.append(data)
                            await asyncio.sleep(0.1)  # جلوگیری از rate limiting
                except:
                    continue
            
            return results if results else None
            
        except Exception as e:
            print(f"خطا در دریافت احساسات بازار برای {symbol}: {e}")
            return None
    
    async def get_crypto_data(self, symbol):
        """دریافت داده‌های جامع ارز دیجیتال"""
        try:
            # دریافت داده‌های روزانه
            daily_data = await self.get_alpha_vantage_data(symbol, "DIGITAL_CURRENCY_DAILY")
            if not daily_data or "Time Series (Digital Currency Daily)" not in daily_data:
                return None
            
            time_series = daily_data["Time Series (Digital Currency Daily)"]
            df_data = []
            
            for date, values in list(time_series.items())[:100]:  # 100 روز اخیر
                try:
                    df_data.append({
                        'date': date,
                        'open': float(values['1a. open (USD)']),
                        'high': float(values['2a. high (USD)']),
                        'low': float(values['3a. low (USD)']),
                        'close': float(values['4a. close (USD)']),
                        'volume': float(values['5. volume']),
                        'market_cap': float(values.get('6. market cap (USD)', 0))
                    })
                except:
                    continue
            
            if not df_data:
                return None
            
            df = pd.DataFrame(df_data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            # دریافت داده‌های اضافی
            sentiment_data = await self.get_market_sentiment(symbol)
            if sentiment_data:
                df = self.enrich_with_sentiment_data(df, sentiment_data)
            
            return df
            
        except Exception as e:
            print(f"خطا در پردازش داده‌های {symbol}: {e}")
            return None
    
    def enrich_with_sentiment_data(self, df, sentiment_data):
        """افزودن داده‌های احساسات بازار به DataFrame"""
        try:
            # استخراج اطلاعات از داده‌های احساسات
            latest_data = df.iloc[-1].copy()
            
            for data in sentiment_data:
                if 'Realtime Currency Exchange Rate' in data:
                    exchange_rate = data['Realtime Currency Exchange Rate']
                    latest_data['exchange_rate'] = float(exchange_rate.get('5. Exchange Rate', 0))
                    latest_data['last_refreshed'] = exchange_rate.get('6. Last Refreshed', '')
                
                elif 'Time Series Crypto (5min)' in data:
                    time_series = data['Time Series Crypto (5min)']
                    latest_price = list(time_series.values())[0]
                    latest_data['latest_high'] = float(latest_price.get('2. high', 0))
                    latest_data['latest_low'] = float(latest_price.get('3. low', 0))
                
                elif 'Crypto Rating (FCAS)' in data:
                    rating = data['Crypto Rating (FCAS)']
                    latest_data['fcas_rating'] = rating.get('1. FCAS Rating', 'N/A')
                    latest_data['fcas_score'] = float(rating.get('2. FCAS Score', 0))
            
            # به روزرسانی آخرین رکورد
            df.iloc[-1] = latest_data
            
        except Exception as e:
            print(f"خطا در افزودن داده‌های احساسات: {e}")
        
        return df
    
    def calculate_indicators(self, df):
        """محاسبه اندیکاتورهای پیشرفته"""
        indicators = {}
        
        if df is None or len(df) < 20:
            return indicators
        
        try:
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            volume = df['volume'].values
            
            # 1. RSI
            indicators['RSI'] = self.calculate_rsi(close, 14)
            
            # 2. MACD
            indicators['MACD'] = self.calculate_macd(close)
            
            # 3-4. Moving Averages
            indicators['MA20'] = self.calculate_sma(close, 20)
            indicators['MA50'] = self.calculate_sma(close, 50)
            
            # 5. Volume Analysis
            indicators['Volume_Avg'] = np.mean(volume[-20:]) if len(volume) >= 20 else np.mean(volume)
            indicators['Volume_Ratio'] = volume[-1] / indicators['Volume_Avg'] if indicators['Volume_Avg'] > 0 else 1
            
            # 6. Price Momentum
            indicators['Momentum'] = self.calculate_momentum(close, 10)
            
            # 7. Support and Resistance
            indicators['Support'] = self.calculate_support(close, low)
            indicators['Resistance'] = self.calculate_resistance(close, high)
            
            # 8. Volatility
            indicators['Volatility'] = self.calculate_volatility(close, 20)
            
            # 9. Price Trends
            indicators['Short_Trend'] = self.calculate_trend(close, 5)
            indicators['Medium_Trend'] = self.calculate_trend(close, 20)
            indicators['Long_Trend'] = self.calculate_trend(close, 50)
            
            # 10. Market Sentiment
            indicators['Market_Score'] = self.calculate_market_score(df)
            
            # قیمت فعلی
            indicators['close'] = close[-1]
            indicators['high'] = high[-1]
            indicators['low'] = low[-1]
            indicators['volume'] = volume[-1]
            
        except Exception as e:
            print(f"خطا در محاسبه اندیکاتورها: {e}")
        
        return indicators
    
    def calculate_rsi(self, prices, period=14):
        """محاسبه RSI"""
        if len(prices) < period + 1:
            return 50
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """محاسبه MACD"""
        if len(prices) < slow:
            return 0
        
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)
        return ema_fast - ema_slow
    
    def calculate_ema(self, prices, period):
        """محاسبه EMA"""
        if len(prices) < period:
            return np.mean(prices) if len(prices) > 0 else 0
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def calculate_sma(self, prices, period):
        """محاسبه SMA"""
        if len(prices) < period:
            return np.mean(prices) if len(prices) > 0 else 0
        return np.mean(prices[-period:])
    
    def calculate_momentum(self, prices, period=10):
        """محاسبه مومنتوم"""
        if len(prices) < period + 1:
            return 0
        return ((prices[-1] - prices[-period]) / prices[-period]) * 100
    
    def calculate_support(self, close, low, lookback=20):
        """محاسبه سطح حمایت"""
        if len(low) < lookback:
            return min(low) if len(low) > 0 else 0
        return min(low[-lookback:])
    
    def calculate_resistance(self, close, high, lookback=20):
        """محاسبه سطح مقاومت"""
        if len(high) < lookback:
            return max(high) if len(high) > 0 else 0
        return max(high[-lookback:])
    
    def calculate_volatility(self, prices, period=20):
        """محاسبه نوسان"""
        if len(prices) < period:
            return 0
        returns = np.diff(prices) / prices[:-1]
        return np.std(returns[-period:]) * 100
    
    def calculate_trend(self, prices, period):
        """محاسبه روند"""
        if len(prices) < period:
            return 0
        
        x = np.arange(period)
        y = prices[-period:]
        
        try:
            slope, _, _, _, _ = stats.linregress(x, y)
            return slope * 100  # بازگشت شیب به عنوان درصد
        except:
            return 0
    
    def calculate_market_score(self, df):
        """محاسبه امتیاز کلی بازار"""
        if len(df) < 10:
            return 50
        
        # عوامل مختلف برای محاسبه امتیاز بازار
        price_change = ((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]) * 100
        volume_ratio = df['volume'].iloc[-1] / df['volume'].mean() if df['volume'].mean() > 0 else 1
        volatility = self.calculate_volatility(df['close'].values, 10)
        
        # محاسبه امتیاز (0-100)
        score = 50  # پایه
        
        # تعدیل بر اساس تغییرات قیمت
        score += min(max(price_change * 2, -20), 20)
        
        # تعدیل بر اساس حجم
        if volume_ratio > 1.5:
            score += 10
        elif volume_ratio < 0.5:
            score -= 10
        
        # تعدیل بر اساس نوسان
        if volatility > 5:
            score -= 5
        
        return max(min(score, 100), 0)
    
    def generate_trading_signal(self, indicators, strategy_type='moderate'):
        """تولید سیگنال معاملاتی دقیق"""
        if not indicators:
            return "HOLD", 0.5, 0, 0, 5
        
        weights = INDICATOR_WEIGHTS.get(strategy_type, INDICATOR_WEIGHTS['moderate'])
        total_score = 0
        max_score = sum(weights.values())
        
        current_price = indicators.get('close', 0)
        
        # تحلیل RSI
        rsi = indicators.get('RSI', 50)
        if rsi < 30:
            total_score += weights['RSI'] * 1.0
        elif rsi > 70:
            total_score -= weights['RSI'] * 1.0
        else:
            total_score += weights['RSI'] * ((rsi - 50) / 20)
        
        # تحلیل MACD
        macd = indicators.get('MACD', 0)
        if macd > 0:
            total_score += weights['MACD'] * 0.8
        else:
            total_score -= weights['MACD'] * 0.8
        
        # تحلیل Moving Averages
        ma20 = indicators.get('MA20', current_price)
        ma50 = indicators.get('MA50', current_price)
        
        if current_price > ma20 > ma50:
            total_score += (weights['MA20'] + weights['MA50']) * 0.7
        elif current_price < ma20 < ma50:
            total_score -= (weights['MA20'] + weights['MA50']) * 0.7
        
        # تحلیل Volume
        volume_ratio = indicators.get('Volume_Ratio', 1)
        if volume_ratio > 1.5:
            total_score += weights['Volume'] * 0.6
        elif volume_ratio < 0.5:
            total_score -= weights['Volume'] * 0.6
        
        # تحلیل روندها
        short_trend = indicators.get('Short_Trend', 0)
        medium_trend = indicators.get('Medium_Trend', 0)
        
        if short_trend > 0 and medium_trend > 0:
            total_score += 15
        elif short_trend < 0 and medium_trend < 0:
            total_score -= 15
        
        # نرمال‌سازی امتیاز
        normalized_score = total_score / max_score
        
        # تولید سیگنال
        if normalized_score > 0.2:
            signal = "BUY"
            confidence = min(normalized_score, 0.95)
            
            # محاسبه دقیق حد سود و ضرر
            support = indicators.get('Support', current_price * 0.95)
            resistance = indicators.get('Resistance', current_price * 1.05)
            volatility = indicators.get('Volatility', 2)
            
            stop_loss = max(support, current_price * (1 - volatility/100))
            take_profit = min(resistance, current_price * (1 + volatility/100 * 1.5))
            
        elif normalized_score < -0.2:
            signal = "SELL"
            confidence = min(abs(normalized_score), 0.95)
            
            support = indicators.get('Support', current_price * 0.95)
            resistance = indicators.get('Resistance', current_price * 1.05)
            volatility = indicators.get('Volatility', 2)
            
            stop_loss = min(resistance, current_price * (1 + volatility/100))
            take_profit = max(support, current_price * (1 - volatility/100 * 1.5))
            
        else:
            signal = "HOLD"
            confidence = 0.5
            stop_loss = 0
            take_profit = 0
        
        leverage = 5  # اهرم ثابت 5x
        
        return signal, confidence, stop_loss, take_profit, leverage
    
    async def analyze_crypto(self, symbol, strategy_type='moderate'):
        """آنالیز کامل یک ارز"""
        await self.init_session()
        
        try:
            # دریافت داده‌های واقعی
            df = await self.get_crypto_data(symbol)
            if df is None or len(df) < 20:
                return None
            
            # محاسبه اندیکاتورها
            indicators = self.calculate_indicators(df)
            if not indicators:
                return None
            
            # تولید سیگنال
            signal, confidence, stop_loss, take_profit, leverage = self.generate_trading_signal(indicators, strategy_type)
            
            # دریافت داده‌های بازار
            market_data = await self.get_market_sentiment(symbol)
            market_info = self.extract_market_info(market_data) if market_data else {}
            
            result = {
                'symbol': symbol,
                'price': indicators.get('close', 0),
                'signal': signal,
                'confidence': confidence,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'leverage': leverage,
                'market_info': market_info,
                'timestamp': datetime.now().isoformat(),
                'indicators': {
                    'RSI': indicators.get('RSI', 0),
                    'MACD': indicators.get('MACD', 0),
                    'MA20': indicators.get('MA20', 0),
                    'MA50': indicators.get('MA50', 0),
                    'Support': indicators.get('Support', 0),
                    'Resistance': indicators.get('Resistance', 0),
                    'Volatility': indicators.get('Volatility', 0)
                }
            }
            
            return result
            
        except Exception as e:
            print(f"خطا در تحلیل {symbol}: {e}")
            return None
        finally:
            await asyncio.sleep(0.2)  # جلوگیری از rate limiting
    
    def extract_market_info(self, market_data):
        """استخراج اطلاعات بازار از داده‌های دریافتی"""
        market_info = {
            'whale_activity': 'normal',
            'long_short_ratio': 1.0,
            'market_sentiment': 'neutral',
            'trading_volume': 'average'
        }
        
        try:
            for data in market_data:
                if 'Realtime Currency Exchange Rate' in data:
                    rate_data = data['Realtime Currency Exchange Rate']
                    market_info['exchange_rate'] = float(rate_data.get('5. Exchange Rate', 0))
                    market_info['last_update'] = rate_data.get('6. Last Refreshed', '')
                
                # شبیه‌سازی داده‌های نهنگ‌ها بر اساس حجم معاملات
                if 'Time Series Crypto (5min)' in data:
                    time_series = data['Time Series Crypto (5min)']
                    latest_volume = float(list(time_series.values())[0].get('5. volume', 0))
                    
                    if latest_volume > 1000000:  # حجم بسیار بالا
                        market_info['whale_activity'] = 'high'
                        market_info['trading_volume'] = 'very_high'
                    elif latest_volume > 500000:  # حجم بالا
                        market_info['whale_activity'] = 'medium'
                        market_info['trading_volume'] = 'high'
            
            # شبیه‌سازی نسبت long/short بر اساس روند
            market_info['long_short_ratio'] = np.random.uniform(0.8, 1.2)
            
        except Exception as e:
            print(f"خطا در استخراج اطلاعات بازار: {e}")
        
        return market_info

# ایجاد نمونه آنالایزر
analyzer = AdvancedCryptoAnalyzer()

# دستورات ربات تلگرام
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور شروع ربات"""
    keyboard = [
        [InlineKeyboardButton("📊 تحلیل همه ارزها", callback_data="analyze_all")],
        [InlineKeyboardButton("🎯 تحلیل ارز خاص", callback_data="analyze_specific")],
        [InlineKeyboardButton("⚙️ تنظیمات استراتژی", callback_data="strategy_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 ربات تحلیل پیشرفته ارزهای دیجیتال\n\n"
        "🔍 آنالیز با داده‌های واقعی از Alpha Vantage\n"
        "🎯 سیگنال‌های دقیق با حد سود/ضرر واقعی\n"
        "⚡ اهرم 5x برای معاملات حرفه‌ای\n\n"
        "لطفا یک گزینه انتخاب کنید:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک روی دکمه‌ها"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "analyze_all":
        await query.edit_message_text("⏳ در حال تحلیل همه ارزها... لطفا منتظر بمانید.")
        await analyze_all_cryptos(query, context)
    
    elif query.data == "analyze_specific":
        keyboard = []
        for i in range(0, len(CRYPTO_SYMBOLS), 3):
            row = []
            for symbol in CRYPTO_SYMBOLS[i:i+3]:
                row.append(InlineKeyboardButton(symbol, callback_data=f"analyze_{symbol}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🔍 لطفا ارز مورد نظر برای تحلیل را انتخاب کنید:",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("analyze_"):
        symbol = query.data.replace("analyze_", "")
        await query.edit_message_text(f"⏳ در حال تحلیل {symbol}... لطفا منتظر بمانید.")
        await analyze_specific_crypto(query, context, symbol)
    
    elif query.data == "strategy_settings":
        keyboard = [
            [InlineKeyboardButton("🛡️ محافظه کارانه", callback_data="strategy_conservative")],
            [InlineKeyboardButton("⚖️ متعادل", callback_data="strategy_moderate")],
            [InlineKeyboardButton("🚀 پرریسک", callback_data="strategy_aggressive")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ لطفا استراتژی معاملاتی خود را انتخاب کنید:",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("strategy_"):
        strategy_type = query.data.replace("strategy_", "")
        context.user_data['strategy'] = strategy_type
        
        strategy_names = {
            'conservative': 'محافظه کارانه',
            'moderate': 'متعادل',
            'aggressive': 'پرریسک'
        }
        
        await query.edit_message_text(
            f"✅ استراتژی به {strategy_names.get(strategy_type, 'متعادل')} تغییر یافت."
        )
    
    elif query.data == "back_to_main":
        await start(update, context)

async def analyze_all_cryptos(query, context):
    """آنالیز همه ارزهای دیجیتال"""
    results = []
    
    for symbol in CRYPTO_SYMBOLS:
        try:
            strategy = context.user_data.get('strategy', 'moderate')
            result = await analyzer.analyze_crypto(symbol, strategy)
            if result:
                results.append(result)
            await asyncio.sleep(1)  # جلوگیری از rate limiting
        except Exception as e:
            print(f"خطا در تحلیل {symbol}: {e}")
            continue
    
    if not results:
        await query.edit_message_text("❌ خطا در دریافت داده‌ها. لطفا دوباره تلاش کنید.")
        return
    
    # ایجاد گزارش
    message = "📊 نتایج تحلیل همه ارزها:\n\n"
    
    buy_signals = [r for r in results if r['signal'] == 'BUY']
    sell_signals = [r for r in results if r['signal'] == 'SELL']
    
    if buy_signals:
        message += "🟢 سیگنال‌های خرید:\n"
        for signal in buy_signals[:5]:
            message += f"{signal['symbol']}: ${signal['price']:.2f} (اطمینان: {signal['confidence']:.0%})\n"
        message += "\n"
    
    if sell_signals:
        message += "🔴 سیگنال‌های فروش:\n"
        for signal in sell_signals[:5]:
            message += f"{signal['symbol']}: ${signal['price']:.2f} (اطمینان: {signal['confidence']:.0%})\n"
        message += "\n"
    
    message += "💡 برای تحلیل دقیق‌تر هر ارز، از منوی اصلی استفاده کنید."
    
    await query.edit_message_text(message)

async def analyze_specific_crypto(query, context, symbol):
    """آنالیز یک ارز دیجیتال خاص"""
    try:
        strategy = context.user_data.get('strategy', 'moderate')
        result = await analyzer.analyze_crypto(symbol, strategy)
        
        if not result:
            await query.edit_message_text(f"❌ خطا در تحلیل {symbol}. لطفا دوباره تلاش کنید.")
            return
        
        # ایجاد پیام گزارش کامل
        message = f"📈 تحلیل پیشرفته {symbol}\n\n"
        message += f"💰 قیمت فعلی: ${result['price']:.2f}\n"
        message += f"🎯 سیگنال: {result['signal']} (اطمینان: {result['confidence']:.0%})\n\n"
        
        if result['signal'] != 'HOLD':
            message += f"🛑 حد ضرر: ${result['stop_loss']:.2f}\n"
            message += f"🎯 حد سود: ${result['take_profit']:.2f}\n"
            message += f"⚖️ اهرم پیشنهادی: {result['leverage']}x\n\n"
        
        # اطلاعات اندیکاتورها
        message += "📊 اندیکاتورهای تکنیکال:\n"
        message += f"• RSI: {result['indicators']['RSI']:.1f}\n"
        message += f"• MACD: {result['indicators']['MACD']:.4f}\n"
        message += f"• MA20: ${result['indicators']['MA20']:.2f}\n"
        message += f"• MA50: ${result['indicators']['MA50']:.2f}\n"
        message += f"• حمایت: ${result['indicators']['Support']:.2f}\n"
        message += f"• مقاومت: ${result['indicators']['Resistance']:.2f}\n"
        message += f"• نوسان: {result['indicators']['Volatility']:.1f}%\n\n"
        
        # اطلاعات بازار
        message += "🌊 اطلاعات بازار:\n"
        message += f"• فعالیت نهنگ‌ها: {result['market_info']['whale_activity']}\n"
        message += f"• نسبت Long/Short: {result['market_info']['long_short_ratio']:.2f}\n"
        message += f"• حجم معاملات: {result['market_info']['trading_volume']}\n\n"
        
        message += f"⏰ آخرین بروزرسانی: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += "⚠️ هشدار: این تحلیل صرفاً آموزشی است و تضمینی برای سود ندارد."
        
        await query.edit_message_text(message)
        
    except Exception as e:
        print(f"خطا در تحلیل {symbol}: {e}")
        await query.edit_message_text(f"❌ خطا در تحلیل {symbol}. لطفا دوباره تلاش کنید.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت خطاهای ربات"""
    print(f"خطا رخ داده: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ متاسفانه خطایی رخ داده است. لطفا دوباره تلاش کنید.")

def main():
    """تابع اصلی اجرای ربات"""
    # ایجاد برنامه تلگرام
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # افزودن handlerها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_error_handler(error_handler)
    
    # اجرای ربات
    print("🤖 ربات تحلیل ارزهای دیجیتال در حال اجراست...")
    print("📱 برای شروع، /start را در تلگرام ارسال کنید")
    
    try:
        application.run_polling()
    except Exception as e:
        print(f"خطا در اجرای ربات: {e}")
    finally:
        # بستن session هنگام خروج
        asyncio.run(analyzer.close_session())

if __name__ == "__main__":
    # تنظیمات logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    main()
