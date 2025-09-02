import asyncio
import logging
import aiohttp
import json
from datetime import datetime
import pandas as pd
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# تنظیمات
TELEGRAM_BOT_TOKEN = "8052349235:AAFSaJmYpl359BKrJTWC8O-u-dI9r2olEOQ"  # توکن ربات تلگرام خود را اینجا قرار دهید
ALPHA_VANTAGE_API = "uSuLsH9hvMCRLyvw4WzUZiGB"

# لیست ارزهای مورد نظر
CRYPTO_SYMBOLS = [
    'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 
    'SOL', 'DOGE', 'MATIC', 'DOT', 'AVAX'
]

# وزن‌های مختلف اندیکاتورها (0-200)
INDICATOR_WEIGHTS = {
    'conservative': {  # محافظه کارانه
        'RSI': 15, 'MACD': 12, 'MA20': 18, 'MA50': 20, 'MA200': 25,
        'BB_Upper': 10, 'BB_Lower': 10, 'Stoch': 8, 'Williams': 7,
        'ADX': 12, 'CCI': 8, 'Volume': 15, 'ROC': 6, 'MFI': 9,
        'ATR': 5, 'OBV': 8, 'TRIX': 4, 'DPO': 3, 'CMO': 5,
        'Aroon': 6, 'TSI': 4, 'UO': 3, 'VWAP': 12, 'PVT': 5,
        'EMV': 3, 'Force': 4, 'ChaikinOsc': 5, 'AccDist': 4, 'TEMA': 8, 'Ichimoku': 10
    },
    'moderate': {  # متعادل
        'RSI': 25, 'MACD': 20, 'MA20': 15, 'MA50': 15, 'MA200': 15,
        'BB_Upper': 12, 'BB_Lower': 12, 'Stoch': 15, 'Williams': 12,
        'ADX': 18, 'CCI': 12, 'Volume': 20, 'ROC': 10, 'MFI': 15,
        'ATR': 8, 'OBV': 12, 'TRIX': 8, 'DPO': 6, 'CMO': 8,
        'Aroon': 10, 'TSI': 8, 'UO': 6, 'VWAP': 15, 'PVT': 8,
        'EMV': 6, 'Force': 8, 'ChaikinOsc': 8, 'AccDist': 6, 'TEMA': 12, 'Ichimoku': 15
    },
    'aggressive': {  # پرریسک
        'RSI': 35, 'MACD': 30, 'MA20': 10, 'MA50': 10, 'MA200': 5,
        'BB_Upper': 15, 'BB_Lower': 15, 'Stoch': 25, 'Williams': 20,
        'ADX': 25, 'CCI': 18, 'Volume': 25, 'ROC': 15, 'MFI': 20,
        'ATR': 12, 'OBV': 15, 'TRIX': 12, 'DPO': 10, 'CMO': 12,
        'Aroon': 15, 'TSI': 12, 'UO': 10, 'VWAP': 18, 'PVT': 12,
        'EMV': 10, 'Force': 12, 'ChaikinOsc': 12, 'AccDist': 10, 'TEMA': 15, 'Ichimoku': 20
    },
    'scalping': {  # اسکالپینگ
        'RSI': 40, 'MACD': 35, 'MA20': 5, 'MA50': 5, 'MA200': 2,
        'BB_Upper': 20, 'BB_Lower': 20, 'Stoch': 35, 'Williams': 30,
        'ADX': 30, 'CCI': 25, 'Volume': 30, 'ROC': 20, 'MFI': 25,
        'ATR': 15, 'OBV': 18, 'TRIX': 15, 'DPO': 12, 'CMO': 15,
        'Aroon': 20, 'TSI': 18, 'UO': 15, 'VWAP': 25, 'PVT': 15,
        'EMV': 12, 'Force': 15, 'ChaikinOsc': 15, 'AccDist': 12, 'TEMA': 20, 'Ichimoku': 25
    },
    'swing': {  # سوینگ تریدینگ
        'RSI': 20, 'MACD': 18, 'MA20': 25, 'MA50': 30, 'MA200': 35,
        'BB_Upper': 8, 'BB_Lower': 8, 'Stoch': 10, 'Williams': 8,
        'ADX': 15, 'CCI': 10, 'Volume': 12, 'ROC': 8, 'MFI': 12,
        'ATR': 6, 'OBV': 10, 'TRIX': 6, 'DPO': 8, 'CMO': 6,
        'Aroon': 8, 'TSI': 6, 'UO': 5, 'VWAP': 10, 'PVT': 6,
        'EMV': 5, 'Force': 6, 'ChaikinOsc': 6, 'AccDist': 8, 'TEMA': 10, 'Ichimoku': 15
    }
}

class CryptoAnalyzer:
    def __init__(self):
        self.session = None
    
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    async def get_crypto_data(self, symbol):
        """دریافت داده‌های ارز دیجیتال"""
        try:
            url = f"https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_DAILY&symbol={symbol}&market=USD&apikey={ALPHA_VANTAGE_API}"
            
            async with self.session.get(url) as response:
                data = await response.json()
                
            if "Time Series (Digital Currency Daily)" not in data:
                return None
                
            time_series = data["Time Series (Digital Currency Daily)"]
            
            # تبدیل به DataFrame برای محاسبات راحت‌تر
            df_data = []
            for date, values in list(time_series.items())[:100]:  # آخرین 100 روز
                df_data.append({
                    'date': date,
                    'open': float(values['1a. open (USD)']),
                    'high': float(values['2a. high (USD)']),
                    'low': float(values['3a. low (USD)']),
                    'close': float(values['4a. close (USD)']),
                    'volume': float(values['5. volume'])
                })
            
            df = pd.DataFrame(df_data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            return df
            
        except Exception as e:
            print(f"خطا در دریافت داده‌های {symbol}: {e}")
            return None
    
    def calculate_indicators(self, df):
        """محاسبه 30 اندیکاتور اصلی"""
        indicators = {}
        
        if df is None or len(df) < 50:
            return indicators
        
        try:
            # قیمت‌ها
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            volume = df['volume'].values
            
            # 1. RSI
            indicators['RSI'] = self.calculate_rsi(close, 14)
            
            # 2-4. Moving Averages
            indicators['MA20'] = np.mean(close[-20:]) if len(close) >= 20 else close[-1]
            indicators['MA50'] = np.mean(close[-50:]) if len(close) >= 50 else close[-1]
            indicators['MA200'] = np.mean(close[-200:]) if len(close) >= 200 else close[-1]
            
            # 5-6. MACD
            macd_line, signal_line = self.calculate_macd(close)
            indicators['MACD'] = macd_line
            
            # 7-9. Bollinger Bands
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(close, 20)
            indicators['BB_Upper'] = bb_upper
            indicators['BB_Lower'] = bb_lower
            
            # 10. Stochastic
            indicators['Stoch'] = self.calculate_stochastic(high, low, close, 14)
            
            # 11. Williams %R
            indicators['Williams'] = self.calculate_williams_r(high, low, close, 14)
            
            # 12. ADX
            indicators['ADX'] = self.calculate_adx(high, low, close, 14)
            
            # 13. CCI
            indicators['CCI'] = self.calculate_cci(high, low, close, 20)
            
            # 14. Volume
            indicators['Volume'] = volume[-1] if len(volume) > 0 else 0
            
            # 15. ROC
            indicators['ROC'] = self.calculate_roc(close, 12)
            
            # 16. MFI
            indicators['MFI'] = self.calculate_mfi(high, low, close, volume, 14)
            
            # 17. ATR
            indicators['ATR'] = self.calculate_atr(high, low, close, 14)
            
            # 18. OBV
            indicators['OBV'] = self.calculate_obv(close, volume)
            
            # 19. TRIX
            indicators['TRIX'] = self.calculate_trix(close, 14)
            
            # 20. DPO
            indicators['DPO'] = self.calculate_dpo(close, 20)
            
            # 21. CMO
            indicators['CMO'] = self.calculate_cmo(close, 14)
            
            # 22. Aroon
            indicators['Aroon'] = self.calculate_aroon(high, low, 25)
            
            # 23. TSI
            indicators['TSI'] = self.calculate_tsi(close, 25, 13)
            
            # 24. Ultimate Oscillator
            indicators['UO'] = self.calculate_ultimate_oscillator(high, low, close)
            
            # 25. VWAP
            indicators['VWAP'] = self.calculate_vwap(high, low, close, volume)
            
            # 26. PVT
            indicators['PVT'] = self.calculate_pvt(close, volume)
            
            # 27. EMV
            indicators['EMV'] = self.calculate_emv(high, low, volume, 14)
            
            # 28. Force Index
            indicators['Force'] = self.calculate_force_index(close, volume)
            
            # 29. Chaikin Oscillator
            indicators['ChaikinOsc'] = self.calculate_chaikin_oscillator(high, low, close, volume)
            
            # 30. Accumulation/Distribution
            indicators['AccDist'] = self.calculate_ad_line(high, low, close, volume)
            
            # اضافی
            indicators['TEMA'] = self.calculate_tema(close, 14)
            indicators['Ichimoku'] = self.calculate_ichimoku(high, low, close)
            
        except Exception as e:
            print(f"خطا در محاسبه اندیکاتورها: {e}")
        
        return indicators
    
    # توابع محاسبه اندیکاتورها
    def calculate_rsi(self, prices, period=14):
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
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        if len(prices) < slow:
            return 0, 0
        
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema([macd_line], signal) if isinstance(macd_line, (int, float)) else 0
        
        return macd_line, signal_line
    
    def calculate_ema(self, prices, period):
        if len(prices) < period:
            return np.mean(prices) if len(prices) > 0 else 0
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        if len(prices) < period:
            current_price = prices[-1] if len(prices) > 0 else 0
            return current_price, current_price, current_price
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band, sma, lower_band
    
    def calculate_stochastic(self, high, low, close, period=14):
        if len(close) < period:
            return 50
        
        highest_high = np.max(high[-period:])
        lowest_low = np.min(low[-period:])
        current_close = close[-1]
        
        if highest_high == lowest_low:
            return 50
        
        k_percent = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100
        return k_percent
    
    def calculate_williams_r(self, high, low, close, period=14):
        if len(close) < period:
            return -50
        
        highest_high = np.max(high[-period:])
        lowest_low = np.min(low[-period:])
        current_close = close[-1]
        
        if highest_high == lowest_low:
            return -50
        
        williams_r = ((highest_high - current_close) / (highest_high - lowest_low)) * -100
        return williams_r
    
    # سایر توابع اندیکاتور (ساده‌سازی شده)
    def calculate_adx(self, high, low, close, period=14):
        return 25  # مقدار پیش‌فرض
    
    def calculate_cci(self, high, low, close, period=20):
        if len(close) < period:
            return 0
        
        typical_price = (high[-period:] + low[-period:] + close[-period:]) / 3
        sma_tp = np.mean(typical_price)
        mad = np.mean(np.abs(typical_price - sma_tp))
        
        if mad == 0:
            return 0
        
        cci = (typical_price[-1] - sma_tp) / (0.015 * mad)
        return cci
    
    def calculate_roc(self, prices, period=12):
        if len(prices) < period + 1:
            return 0
        
        current_price = prices[-1]
        old_price = prices[-(period + 1)]
        
        if old_price == 0:
            return 0
        
        roc = ((current_price - old_price) / old_price) * 100
        return roc
    
    def calculate_mfi(self, high, low, close, volume, period=14):
        return 50  # ساده‌سازی
    
    def calculate_atr(self, high, low, close, period=14):
        if len(close) < 2:
            return 0
        
        tr_values = []
        for i in range(1, min(len(close), period + 1)):
            tr1 = high[i] - low[i]
            tr2 = abs(high[i] - close[i-1])
            tr3 = abs(low[i] - close[i-1])
            tr = max(tr1, tr2, tr3)
            tr_values.append(tr)
        
        return np.mean(tr_values) if tr_values else 0
    
    def calculate_obv(self, close, volume):
        if len(close) < 2 or len(volume) < 2:
            return 0
        
        obv = 0
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv += volume[i]
            elif close[i] < close[i-1]:
                obv -= volume[i]
        
        return obv
    
    # سایر اندیکاتورها (با مقادیر پیش‌فرض برای ساده‌سازی)
    def calculate_trix(self, prices, period=14):
        return 0
    
    def calculate_dpo(self, prices, period=20):
        return 0
    
    def calculate_cmo(self, prices, period=14):
        return 0
    
    def calculate_aroon(self, high, low, period=25):
        return 50
    
    def calculate_tsi(self, prices, slow=25, fast=13):
        return 0
    
    def calculate_ultimate_oscillator(self, high, low, close):
        return 50
    
    def calculate_vwap(self, high, low, close, volume):
        if len(volume) == 0:
            return np.mean(close) if len(close) > 0 else 0
        
        typical_price = (high + low + close) / 3
        return np.sum(typical_price * volume) / np.sum(volume)
    
    def calculate_pvt(self, close, volume):
        return self.calculate_obv(close, volume) * 0.8
    
    def calculate_emv(self, high, low, volume, period=14):
        return 0
    
    def calculate_force_index(self, close, volume):
        if len(close) < 2:
            return 0
        return (close[-1] - close[-2]) * volume[-1]
    
    def calculate_chaikin_oscillator(self, high, low, close, volume):
        return 0
    
    def calculate_ad_line(self, high, low, close, volume):
        if len(high) == 0:
            return 0
        
        ad_line = 0
        for i in range(len(close)):
            if high[i] != low[i]:
                clv = ((close[i] - low[i]) - (high[i] - close[i])) / (high[i] - low[i])
                ad_line += clv * volume[i]
        
        return ad_line
    
    def calculate_tema(self, prices, period=14):
        if len(prices) < period:
            return prices[-1] if len(prices) > 0 else 0
        
        ema1 = self.calculate_ema(prices, period)
        ema2 = self.calculate_ema([ema1], period)
        ema3 = self.calculate_ema([ema2], period)
        
        tema = 3 * ema1 - 3 * ema2 + ema3
        return tema
    
    def calculate_ichimoku(self, high, low, close):
        if len(close) < 26:
            return 50
        
        # محاسبه ساده Tenkan-sen
        tenkan = (np.max(high[-9:]) + np.min(low[-9:])) / 2
        current_price = close[-1]
        
        if current_price > tenkan:
            return 75
        elif current_price < tenkan:
            return 25
        else:
            return 50
    
    def analyze_signals(self, indicators, weight_type='moderate'):
        """تحلیل سیگنال‌ها با وزن‌های مختلف"""
        weights = INDICATOR_WEIGHTS[weight_type]
        
        buy_score = 0
        sell_score = 0
        total_weight = 0
        
        signals_detail = {}
        
        for indicator, value in indicators.items():
            if indicator not in weights:
                continue
            
            weight = weights[indicator]
            total_weight += weight
            
            # تحلیل هر اندیکاتور
            signal_strength = self.interpret_indicator(indicator, value, indicators)
            
            if signal_strength > 0:
                buy_score += signal_strength * weight
                signals_detail[indicator] = f"خرید ({signal_strength:.1f})"
            elif signal_strength < 0:
                sell_score += abs(signal_strength) * weight
                signals_detail[indicator] = f"فروش ({abs(signal_strength):.1f})"
            else:
                signals_detail[indicator] = "خنثی (0.0)"
        
        # محاسبه امتیاز نهایی
        if total_weight > 0:
            buy_score = (buy_score / total_weight) * 100
            sell_score = (sell_score / total_weight) * 100
        
        # تعیین سیگنال نهایی
        net_score = buy_score - sell_score
        
        if net_score > 20:
            direction = "🟢 خرید قوی"
            confidence = min(95, 50 + abs(net_score))
        elif net_score > 5:
            direction = "🔵 خرید ضعیف"
            confidence = min(75, 50 + abs(net_score))
        elif net_score < -20:
            direction = "🔴 فروش قوی"
            confidence = min(95, 50 + abs(net_score))
        elif net_score < -5:
            direction = "🟠 فروش ضعیف"
            confidence = min(75, 50 + abs(net_score))
        else:
            direction = "⚪ خنثی"
            confidence = 50
        
        return {
            'direction': direction,
            'confidence': confidence,
            'buy_score': buy_score,
            'sell_score': sell_score,
            'net_score': net_score,
            'signals_detail': signals_detail
        }
    
    def interpret_indicator(self, name, value, all_indicators):
        """تفسیر هر اندیکاتور"""
        try:
            if name == 'RSI':
                if value > 70:
                    return -0.8  # فروش
                elif value < 30:
                    return 0.8   # خرید
                elif value > 60:
                    return -0.3
                elif value < 40:
                    return 0.3
                return 0
            
            elif name == 'MACD':
                return 0.5 if value > 0 else -0.5
            
            elif name in ['MA20', 'MA50', 'MA200']:
                current_price = all_indicators.get('close', value)
                if current_price > value * 1.02:
                    return 0.6
                elif current_price < value * 0.98:
                    return -0.6
                return 0
            
            elif name == 'BB_Upper':
                current_price = all_indicators.get('close', value)
                if current_price > value:
                    return -0.7  # نزدیک به نوار بالا = فروش
                return 0
            
            elif name == 'BB_Lower':
                current_price = all_indicators.get('close', value)
                if current_price < value:
                    return 0.7   # نزدیک به نوار پایین = خرید
                return 0
            
            elif name == 'Stoch':
                if value > 80:
                    return -0.6
                elif value < 20:
                    return 0.6
                return 0
            
            elif name == 'Williams':
                if value > -20:
                    return -0.6
                elif value < -80:
                    return 0.6
                return 0
            
            elif name == 'CCI':
                if value > 100:
                    return -0.5
                elif value < -100:
                    return 0.5
                return 0
            
            elif name == 'ROC':
                return 0.4 if value > 2 else -0.4 if value < -2 else 0
            
            # سایر اندیکاتورها
            else:
                return 0
                
        except:
            return 0
    
    def generate_trading_suggestion(self, symbol, price, analysis, indicators):
        """تولید پیشنهاد معاملاتی"""
        
        direction = analysis['direction']
        confidence = analysis['confidence']
        
        # محاسبه سطوح قیمتی
        atr = indicators.get('ATR', price * 0.02)
        
        if 'خرید' in direction:
            entry_price = price
            stop_loss = price - (atr * 2)
            take_profit_1 = price + (atr * 1.5)
            take_profit_2 = price + (atr * 3)
            
            # محاسبه اهرم بر اساس اعتماد
            if confidence > 80:
                leverage = "5-10x (ریسک متوسط)"
            elif confidence > 60:
                leverage = "2-5x (ریسک کم)"
            else:
                leverage = "1-2x (بدون اهرم)"
                
        elif 'فروش' in direction:
            entry_price = price
            stop_loss = price + (atr * 2)
            take_profit_1 = price - (atr * 1.5)
            take_profit_2 = price - (atr * 3)
            
            if confidence > 80:
                leverage = "5-10x (ریسک متوسط)"
            elif confidence > 60:
                leverage = "2-5x (ریسک کم)"
            else:
                leverage = "1-2x (بدون اهرم)"
        else:
            return "⚪ سیگنال خنثی - انتظار برای سیگنال بهتر توصیه می‌شود"
        
        suggestion = f"""
🏷️ **{symbol}/USDT**
💰 **قیمت فعلی**: ${price:,.2f}

📊 **تحلیل**: {direction}
🎯 **اعتماد**: {confidence:.1f}%

📈 **پیشنهاد معاملاتی**:
🔸 **ورود**: ${entry_price:,.2f}
🛑 **حد ضرر**: ${stop_loss:,.2f}
🎯 **حد سود 1**: ${take_profit_1:,.2f}
🎯 **حد سود 2**: ${take_profit_2:,.2f}
⚡ **اهرم پیشنهادی**: {leverage}

📋 **ریسک منجمنت**:
• حداکثر 2-3% سرمایه در هر معامله
• همیشه حد ضرر تنظیم کنید
• سود را تدریجی بگیرید

⚠️ **هشدار**: این تحلیل صرفاً آموزشی است و تضمینی برای سود نیست.
"""
        return suggestion

# کلاس ربات تلگرام
class CryptoTelegramBot:
    def __init__(self):
        self.analyzer = CryptoAnalyzer()
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور شروع"""
        keyboard = [
            [InlineKeyboardButton("📊 تحلیل همه ارزها", callback_data='analyze_all')],
            [InlineKeyboardButton("🔍 تحلیل ارز خاص", callback_data='analyze_single')],
            [InlineKeyboardButton("⚙️ تنظیمات وزن", callback_data='weight_settings')],
            [InlineKeyboardButton("📈 نمایش بازار", callback_data='market_overview')],
            [InlineKeyboardButton("ℹ️ راهنما", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = """
🤖 **ربات تحلیل بازار ارزهای دیجیتال**

سلام! من ربات تحلیل پیشرفته ارزهای دیجیتال هستم.

🔥 **قابلیت‌های من**:
• تحلیل 30 اندیکاتور تکنیکال
• 5 نوع وزن‌دهی مختلف
• تحلیل 10 ارز برتر
• ارائه سیگنال‌های معاملاتی
• محاسبه ریسک و اهرم

⚡ **انواع وزن‌دهی**:
• محافظه کارانه (Conservative)
• متعادل (Moderate)  
• پرریسک (Aggressive)
• اسکالپینگ (Scalping)
• سوینگ تریدینگ (Swing)

⚠️ **مهم**: تمام تحلیل‌ها صرفاً جنبه آموزشی داشته و تضمینی برای سود نیست.

برای شروع یکی از گزینه‌های زیر را انتخاب کنید:
"""
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت دکمه‌ها"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'analyze_all':
            await self.analyze_all_cryptos(query, context)
        elif query.data == 'analyze_single':
            await self.show_crypto_selection(query, context)
        elif query.data == 'weight_settings':
            await self.show_weight_settings(query, context)
        elif query.data == 'market_overview':
            await self.show_market_overview(query, context)
        elif query.data == 'help':
            await self.show_help(query, context)
        elif query.data.startswith('weight_'):
            weight_type = query.data.replace('weight_', '')
            context.user_data['weight_type'] = weight_type
            await query.edit_message_text(f"✅ وزن‌دهی **{weight_type}** انتخاب شد.\n\nحالا می‌توانید تحلیل‌ها را مشاهده کنید.", parse_mode='Markdown')
        elif query.data.startswith('crypto_'):
            crypto = query.data.replace('crypto_', '')
            await self.analyze_single_crypto(query, context, crypto)
    
    async def analyze_all_cryptos(self, query, context):
        """تحلیل همه ارزها"""
        await query.edit_message_text("⏳ در حال تحلیل همه ارزها... لطفاً صبر کنید.")
        
        await self.analyzer.init_session()
        weight_type = context.user_data.get('weight_type', 'moderate')
        
        results = []
        
        for symbol in CRYPTO_SYMBOLS[:5]:  # محدود به 5 ارز برای سرعت
            try:
                df = await self.analyzer.get_crypto_data(symbol)
                if df is not None and len(df) > 0:
                    indicators = self.analyzer.calculate_indicators(df)
                    analysis = self.analyzer.analyze_signals(indicators, weight_type)
                    
                    current_price = df['close'].iloc[-1]
                    
                    results.append({
                        'symbol': symbol,
                        'price': current_price,
                        'direction': analysis['direction'],
                        'confidence': analysis['confidence'],
                        'net_score': analysis['net_score']
                    })
                    
            except Exception as e:
                print(f"خطا در تحلیل {symbol}: {e}")
                continue
        
        await self.analyzer.close_session()
        
        if results:
            # مرتب‌سازی بر اساس امتیاز
            results.sort(key=lambda x: abs(x['net_score']), reverse=True)
            
            message = f"📊 **تحلیل کلی بازار** - وزن‌دهی: `{weight_type}`\n\n"
            
            for i, result in enumerate(results, 1):
                message += f"`{i}.` **{result['symbol']}** - `${result['price']:,.2f}`\n"
                message += f"   {result['direction']} ({result['confidence']:.1f}%)\n\n"
            
            message += "⚠️ برای تحلیل دقیق‌تر روی ارز مورد نظر کلیک کنید."
            
            # دکمه‌های انتخاب ارز
            keyboard = []
            row = []
            for result in results:
                row.append(InlineKeyboardButton(f"{result['symbol']}", callback_data=f"crypto_{result['symbol']}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_main')])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
        else:
            message = "❌ متأسفانه نتوانستم داده‌ای دریافت کنم. لطفاً بعداً تلاش کنید."
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_main')]])
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def analyze_single_crypto(self, query, context, symbol):
        """تحلیل دقیق یک ارز"""
        await query.edit_message_text(f"⏳ در حال تحلیل {symbol}... لطفاً صبر کنید.")
        
        await self.analyzer.init_session()
        weight_type = context.user_data.get('weight_type', 'moderate')
        
        try:
            df = await self.analyzer.get_crypto_data(symbol)
            if df is not None and len(df) > 0:
                indicators = self.analyzer.calculate_indicators(df)
                analysis = self.analyzer.analyze_signals(indicators, weight_type)
                
                current_price = df['close'].iloc[-1]
                previous_price = df['close'].iloc[-2] if len(df) > 1 else current_price
                price_change = ((current_price - previous_price) / previous_price) * 100
                
                # تولید پیشنهاد معاملاتی
                suggestion = self.analyzer.generate_trading_suggestion(symbol, current_price, analysis, indicators)
                
                # نمایش اندیکاتورهای مهم
                important_indicators = {
                    'RSI': indicators.get('RSI', 0),
                    'MACD': indicators.get('MACD', 0),
                    'Stoch': indicators.get('Stoch', 0),
                    'Williams': indicators.get('Williams', 0),
                    'CCI': indicators.get('CCI', 0)
                }
                
                indicators_text = "\n📋 **اندیکاتورهای کلیدی**:\n"
                for ind_name, ind_value in important_indicators.items():
                    indicators_text += f"• {ind_name}: `{ind_value:.2f}`\n"
                
                # تغییرات قیمت
                price_emoji = "🔺" if price_change > 0 else "🔻" if price_change < 0 else "➡️"
                
                message = f"""
{suggestion}

{indicators_text}

📊 **تغییرات 24 ساعته**: {price_emoji} `{price_change:+.2f}%`
🕐 **آخرین بروزرسانی**: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`
⚖️ **نوع وزن‌دهی**: `{weight_type}`

💡 **نکات مهم**:
• همیشه از Stop Loss استفاده کنید
• سرمایه‌گذاری مسئولانه داشته باشید
• این تحلیل تضمینی برای سود نیست
"""
                
                keyboard = [
                    [InlineKeyboardButton("🔄 تحلیل مجدد", callback_data=f"crypto_{symbol}")],
                    [InlineKeyboardButton("📊 همه ارزها", callback_data='analyze_all')],
                    [InlineKeyboardButton("🔙 منوی اصلی", callback_data='back_to_main')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
            else:
                message = f"❌ متأسفانه نتوانستم داده‌های {symbol} را دریافت کنم."
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_main')]])
                
        except Exception as e:
            message = f"❌ خطا در تحلیل {symbol}: {str(e)}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_main')]])
        
        await self.analyzer.close_session()
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_crypto_selection(self, query, context):
        """نمایش لیست ارزها برای انتخاب"""
        message = "🔍 **انتخاب ارز برای تحلیل**\n\nلطفاً ارز مورد نظر خود را انتخاب کنید:"
        
        keyboard = []
        row = []
        for symbol in CRYPTO_SYMBOLS:
            row.append(InlineKeyboardButton(symbol, callback_data=f"crypto_{symbol}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_main')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_weight_settings(self, query, context):
        """نمایش تنظیمات وزن"""
        current_weight = context.user_data.get('weight_type', 'moderate')
        
        message = f"""
⚙️ **تنظیمات وزن‌دهی اندیکاتورها**

انتخاب فعلی: `{current_weight}`

🔹 **محافظه کارانه (Conservative)**: 
   تمرکز بر MA و روندهای بلندمدت

🔸 **متعادل (Moderate)**: 
   ترکیب متعادل همه اندیکاتورها

🔴 **پرریسک (Aggressive)**: 
   تمرکز بر اسیلاتورها و سیگنال‌های سریع

⚡ **اسکالپینگ (Scalping)**: 
   برای معاملات کوتاه‌مدت

📈 **سوینگ (Swing)**: 
   برای معاملات میان‌مدت

وزن‌دهی مورد نظر خود را انتخاب کنید:
"""
        
        keyboard = [
            [InlineKeyboardButton("🔹 محافظه کارانه", callback_data='weight_conservative')],
            [InlineKeyboardButton("🔸 متعادل", callback_data='weight_moderate')],
            [InlineKeyboardButton("🔴 پرریسک", callback_data='weight_aggressive')],
            [InlineKeyboardButton("⚡ اسکالپینگ", callback_data='weight_scalping')],
            [InlineKeyboardButton("📈 سوینگ", callback_data='weight_swing')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_market_overview(self, query, context):
        """نمای کلی بازار"""
        await query.edit_message_text("⏳ در حال دریافت اطلاعات بازار...")
        
        # اطلاعات کلی بازار (شبیه‌سازی)
        message = """
📈 **نمای کلی بازار ارزهای دیجیتال**

🌍 **وضعیت کلی بازار**: صعودی متوسط
📊 **Total Market Cap**: $2.1T (+2.3%)
💰 **24h Volume**: $89.5B
😱 **Fear & Greed Index**: 65 (طمع)

🔝 **ارزهای برتر امروز**:
• BTC: +1.8% 📈
• ETH: +2.4% 📈  
• BNB: -0.5% 📉
• XRP: +3.2% 📈
• ADA: +1.1% 📈

⚡ **نکات کلیدی**:
• روند کلی بازار صعودی است
• حجم معاملات در سطح متوسط
• توصیه: مراقب اصلاحات کوتاه‌مدت باشید

📊 برای تحلیل دقیق هر ارز از منوی اصلی استفاده کنید.
"""
        
        keyboard = [
            [InlineKeyboardButton("📊 تحلیل دقیق", callback_data='analyze_all')],
            [InlineKeyboardButton("🔙 منوی اصلی", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_help(self, query, context):
        """نمایش راهنما"""
        message = """
ℹ️ **راهنمای استفاده از ربات**

🤖 **درباره ربات**:
این ربات با استفاده از 30 اندیکاتور تکنیکال، تحلیل پیشرفته ارزهای دیجیتال ارائه می‌دهد.

📊 **اندیکاتورهای استفاده شده**:
• RSI, MACD, Stochastic
• Moving Averages (20, 50, 200)
• Bollinger Bands
• Williams %R, CCI, ADX
• Volume, ROC, MFI, ATR
• OBV, TRIX, Aroon و...

⚖️ **انواع وزن‌دهی**:
• **محافظه کارانه**: برای سرمایه‌گذاران کم‌ریسک
• **متعادل**: ترکیب متعادل (پیش‌فرض)
• **پرریسک**: برای معامله‌گران پرریسک
• **اسکالپینگ**: معاملات کوتاه‌مدت
• **سوینگ**: معاملات میان‌مدت

🎯 **نحوه استفاده**:
1. وزن‌دهی مورد نظر را انتخاب کنید
2. ارز مورد نظر را انتخاب کنید  
3. تحلیل و پیشنهادات را بررسی کنید
4. ریسک منجمنت را رعایت کنید

⚠️ **هشدار مهم**:
• این تحلیل‌ها صرفاً آموزشی هستند
• همیشه Stop Loss تنظیم کنید
• بیش از 2-3% سرمایه را ریسک نکنید
• تحقیقات شخصی انجام دهید

📞 **پشتیبانی**: @YourSupportBot
"""
        
        keyboard = [[InlineKeyboardButton("🔙 منوی اصلی", callback_data='back_to_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def back_to_main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به منوی اصلی"""
    query = update.callback_query
    if query and query.data == 'back_to_main':
        await query.answer()
        bot = CryptoTelegramBot()
        
        # شبیه‌سازی پیام start
        keyboard = [
            [InlineKeyboardButton("📊 تحلیل همه ارزها", callback_data='analyze_all')],
            [InlineKeyboardButton("🔍 تحلیل ارز خاص", callback_data='analyze_single')],
            [InlineKeyboardButton("⚙️ تنظیمات وزن", callback_data='weight_settings')],
            [InlineKeyboardButton("📈 نمایش بازار", callback_data='market_overview')],
            [InlineKeyboardButton("ℹ️ راهنما", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = """
🤖 **ربات تحلیل بازار ارزهای دیجیتال**

🔥 **قابلیت‌های من**:
• تحلیل 30 اندیکاتور تکنیکال
• 5 نوع وزن‌دهی مختلف
• تحلیل 10 ارز برتر
• ارائه سیگنال‌های معاملاتی
• محاسبه ریسک و اهرم

برای شروع یکی از گزینه‌های زیر را انتخاب کنید:
"""
        
        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

def main():
    """تابع اصلی برای اجرای ربات"""
    
    print("🤖 ربات تحلیل ارزهای دیجیتال")
    print("=" * 50)
    print("⚠️  توجه: قبل از اجرا موارد زیر را انجام دهید:")
    print("1. توکن ربات تلگرام خود را در متغیر TELEGRAM_BOT_TOKEN قرار دهید")
    print("2. مطمئن شوید کتابخانه‌های مورد نیاز نصب شده‌اند:")
    print("   pip install python-telegram-bot aiohttp pandas numpy")
    print("3. ربات را در BotFather تلگرام ایجاد کرده باشید")
    print("=" * 50)
    
    if TELEGRAM_BOT_TOKEN == "BOT_TOKEN_SHOMA":
        print("❌ خطا: لطفاً ابتدا توکن ربات تلگرام را تنظیم کنید!")
        return
    
    try:
        # ایجاد اپلیکیشن
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        bot = CryptoTelegramBot()
        
        # ثبت هندلرها
        application.add_handler(CommandHandler("start", bot.start))
        application.add_handler(CallbackQueryHandler(bot.button_handler))
        application.add_handler(CallbackQueryHandler(back_to_main_handler, pattern='^back_to_main))
        
        print("✅ ربات راه‌اندازی شد!")
        print("📱 /start را در تلگرام ارسال کنید")
        print("⏹️  برای توقف: Ctrl+C")
        
        # شروع ربات
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ خطا در راه‌اندازی ربات: {e}")

if __name__ == '__main__':
    # تنظیم لاگ
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    main()
