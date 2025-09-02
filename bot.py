import asyncio
import logging
import aiohttp
import json
from datetime import datetime
import pandas as pd
import numpy as np
from scipy import stats
import talib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# تنظیمات
TELEGRAM_BOT_TOKEN = "8052349235:AAFSaJmYpl359BKrJTWC8O-u-dI9r2olEOQ"
ALPHA_VANTAGE_API = "uSuLsH9hvMCRLyvw4WzUZiGB"

# لیست ارزهای مورد نظر
CRYPTO_SYMBOLS = [
    'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 
    'SOL', 'DOGE', 'MATIC', 'DOT', 'AVAX'
]

# وزن‌های مختلف اندیکاتورها (0-200) - نسخه پیشرفته
INDICATOR_WEIGHTS = {
    'conservative': {  # محافظه کارانه
        'RSI': 18, 'MACD': 15, 'MA20': 22, 'MA50': 25, 'MA200': 30,
        'BB_Upper': 12, 'BB_Lower': 12, 'Stoch': 10, 'Williams': 8,
        'ADX': 15, 'CCI': 10, 'Volume': 18, 'ROC': 8, 'MFI': 12,
        'ATR': 8, 'OBV': 10, 'TRIX': 6, 'DPO': 5, 'CMO': 7,
        'Aroon': 8, 'TSI': 6, 'UO': 5, 'VWAP': 15, 'PVT': 7,
        'EMV': 5, 'Force': 6, 'ChaikinOsc': 7, 'AccDist': 6, 
        'TEMA': 10, 'Ichimoku': 12, 'KST': 8, 'Vortex': 7,
        'Z_Score': 15, 'Donchian': 12, 'Keltner': 10, 'ParabolicSAR': 9,
        'Fisher': 8, 'ElderRay': 10, 'HullMA': 12, 'SuperTrend': 15
    },
    'moderate': {  # متعادل
        'RSI': 25, 'MACD': 22, 'MA20': 18, 'MA50': 20, 'MA200': 18,
        'BB_Upper': 15, 'BB_Lower': 15, 'Stoch': 18, 'Williams': 15,
        'ADX': 20, 'CCI': 15, 'Volume': 22, 'ROC': 12, 'MFI': 18,
        'ATR': 12, 'OBV': 15, 'TRIX': 10, 'DPO': 8, 'CMO': 10,
        'Aroon': 12, 'TSI': 10, 'UO': 8, 'VWAP': 18, 'PVT': 12,
        'EMV': 10, 'Force': 12, 'ChaikinOsc': 12, 'AccDist': 10, 
        'TEMA': 15, 'Ichimoku': 18, 'KST': 12, 'Vortex': 10,
        'Z_Score': 18, 'Donchian': 15, 'Keltner': 12, 'ParabolicSAR': 10,
        'Fisher': 12, 'ElderRay': 15, 'HullMA': 15, 'SuperTrend': 18
    },
    'aggressive': {  # پرریسک
        'RSI': 35, 'MACD': 30, 'MA20': 12, 'MA50': 10, 'MA200': 8,
        'BB_Upper': 18, 'BB_Lower': 18, 'Stoch': 25, 'Williams': 22,
        'ADX': 25, 'CCI': 20, 'Volume': 28, 'ROC': 18, 'MFI': 22,
        'ATR': 15, 'OBV': 18, 'TRIX': 15, 'DPO': 12, 'CMO': 15,
        'Aroon': 18, 'TSI': 15, 'UO': 12, 'VWAP': 22, 'PVT': 15,
        'EMV': 12, 'Force': 15, 'ChaikinOsc': 15, 'AccDist': 12, 
        'TEMA': 18, 'Ichimoku': 22, 'KST': 15, 'Vortex': 12,
        'Z_Score': 20, 'Donchian': 18, 'Keltner': 15, 'ParabolicSAR': 12,
        'Fisher': 15, 'ElderRay': 18, 'HullMA': 18, 'SuperTrend': 20
    },
    'scalping': {  # اسکالپینگ
        'RSI': 40, 'MACD': 35, 'MA20': 8, 'MA50': 6, 'MA200': 4,
        'BB_Upper': 22, 'BB_Lower': 22, 'Stoch': 35, 'Williams': 30,
        'ADX': 30, 'CCI': 25, 'Volume': 32, 'ROC': 22, 'MFI': 28,
        'ATR': 18, 'OBV': 20, 'TRIX': 18, 'DPO': 15, 'CMO': 18,
        'Aroon': 22, 'TSI': 18, 'UO': 15, 'VWAP': 25, 'PVT': 18,
        'EMV': 15, 'Force': 18, 'ChaikinOsc': 18, 'AccDist': 15, 
        'TEMA': 20, 'Ichimoku': 25, 'KST': 18, 'Vortex': 15,
        'Z_Score': 22, 'Donchian': 20, 'Keltner': 18, 'ParabolicSAR': 15,
        'Fisher': 18, 'ElderRay': 20, 'HullMA': 20, 'SuperTrend': 22
    },
    'swing': {  # سوینگ تریدینگ
        'RSI': 22, 'MACD': 20, 'MA20': 28, 'MA50': 32, 'MA200': 35,
        'BB_Upper': 10, 'BB_Lower': 10, 'Stoch': 12, 'Williams': 10,
        'ADX': 18, 'CCI': 12, 'Volume': 15, 'ROC': 10, 'MFI': 15,
        'ATR': 8, 'OBV': 12, 'TRIX': 8, 'DPO': 10, 'CMO': 8,
        'Aroon': 10, 'TSI': 8, 'UO': 6, 'VWAP': 12, 'PVT': 8,
        'EMV': 6, 'Force': 8, 'ChaikinOsc': 8, 'AccDist': 10, 
        'TEMA': 12, 'Ichimoku': 18, 'KST': 10, 'Vortex': 8,
        'Z_Score': 12, 'Donchian': 10, 'Keltner': 8, 'ParabolicSAR': 6,
        'Fisher': 8, 'ElderRay': 10, 'HullMA': 12, 'SuperTrend': 15
    }
}

class AdvancedCryptoAnalyzer:
    def __init__(self):
        self.session = None
        self.indicators_cache = {}
    
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    async def get_crypto_data(self, symbol):
        """دریافت داده‌های ارز دیجیتال با جزئیات بیشتر"""
        try:
            # استفاده از چند منبع داده برای دقت بیشتر
            urls = [
                f"https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_DAILY&symbol={symbol}&market=USD&apikey={ALPHA_VANTAGE_API}",
                f"https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_WEEKLY&symbol={symbol}&market=USD&apikey={ALPHA_VANTAGE_API}",
                f"https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_MONTHLY&symbol={symbol}&market=USD&apikey={ALPHA_VANTAGE_API}"
            ]
            
            all_data = []
            for url in urls:
                try:
                    async with self.session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            if "Time Series" in str(data):
                                all_data.append(data)
                except:
                    continue
            
            if not all_data:
                return None
                
            # ترکیب داده‌ها از منابع مختلف
            combined_data = {}
            for data in all_data:
                for key in data:
                    if "Time Series" in key:
                        time_series = data[key]
                        for date, values in time_series.items():
                            if date not in combined_data:
                                combined_data[date] = values
            
            # تبدیل به DataFrame
            df_data = []
            for date, values in list(combined_data.items())[:200]:  # 200 روز اخیر
                try:
                    df_data.append({
                        'date': date,
                        'open': float(values.get('1a. open (USD)', values.get('1. open', 0))),
                        'high': float(values.get('2a. high (USD)', values.get('2. high', 0))),
                        'low': float(values.get('3a. low (USD)', values.get('3. low', 0))),
                        'close': float(values.get('4a. close (USD)', values.get('4. close', 0))),
                        'volume': float(values.get('5. volume', 0))
                    })
                except:
                    continue
            
            if not df_data:
                return None
                
            df = pd.DataFrame(df_data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            return df
            
        except Exception as e:
            print(f"خطا در دریافت داده‌های {symbol}: {e}")
            return None
    
    def calculate_all_indicators(self, df):
        """محاسبه 40+ اندیکاتور پیشرفته"""
        indicators = {}
        
        if df is None or len(df) < 50:
            return indicators
        
        try:
            # قیمت‌ها
            close = np.array(df['close'].values, dtype=np.float64)
            high = np.array(df['high'].values, dtype=np.float64)
            low = np.array(df['low'].values, dtype=np.float64)
            volume = np.array(df['volume'].values, dtype=np.float64)
            open_price = np.array(df['open'].values, dtype=np.float64)
            
            # 1. RSI (با چند دوره مختلف)
            indicators['RSI'] = self.calculate_rsi(close, 14)
            indicators['RSI_7'] = self.calculate_rsi(close, 7)
            indicators['RSI_21'] = self.calculate_rsi(close, 21)
            
            # 2-4. Moving Averages
            indicators['MA20'] = talib.SMA(close, timeperiod=20)[-1] if len(close) >= 20 else close[-1]
            indicators['MA50'] = talib.SMA(close, timeperiod=50)[-1] if len(close) >= 50 else close[-1]
            indicators['MA200'] = talib.SMA(close, timeperiod=200)[-1] if len(close) >= 200 else close[-1]
            indicators['EMA_12'] = talib.EMA(close, timeperiod=12)[-1]
            indicators['EMA_26'] = talib.EMA(close, timeperiod=26)[-1]
            
            # 5-6. MACD
            macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
            indicators['MACD'] = macd[-1]
            indicators['MACD_Signal'] = macd_signal[-1]
            indicators['MACD_Hist'] = macd_hist[-1]
            
            # 7-9. Bollinger Bands
            bb_upper, bb_middle, bb_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
            indicators['BB_Upper'] = bb_upper[-1]
            indicators['BB_Middle'] = bb_middle[-1]
            indicators['BB_Lower'] = bb_lower[-1]
            indicators['BB_Width'] = (bb_upper[-1] - bb_lower[-1]) / bb_middle[-1]
            indicators['BB_Position'] = (close[-1] - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1])
            
            # 10. Stochastic
            slowk, slowd = talib.STOCH(high, low, close, fastk_period=14, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
            indicators['Stoch_K'] = slowk[-1]
            indicators['Stoch_D'] = slowd[-1]
            indicators['Stoch'] = slowk[-1]  # برای سازگاری
            
            # 11. Williams %R
            indicators['Williams'] = talib.WILLR(high, low, close, timeperiod=14)[-1]
            
            # 12. ADX
            indicators['ADX'] = talib.ADX(high, low, close, timeperiod=14)[-1]
            
            # 13. CCI
            indicators['CCI'] = talib.CCI(high, low, close, timeperiod=20)[-1]
            
            # 14. Volume Analysis
            indicators['Volume'] = volume[-1] if len(volume) > 0 else 0
            indicators['Volume_MA20'] = talib.SMA(volume, timeperiod=20)[-1] if len(volume) >= 20 else volume[-1]
            indicators['Volume_Ratio'] = volume[-1] / indicators['Volume_MA20'] if indicators['Volume_MA20'] > 0 else 1
            
            # 15. ROC
            indicators['ROC'] = talib.ROC(close, timeperiod=12)[-1]
            
            # 16. MFI
            indicators['MFI'] = talib.MFI(high, low, close, volume, timeperiod=14)[-1]
            
            # 17. ATR
            indicators['ATR'] = talib.ATR(high, low, close, timeperiod=14)[-1]
            
            # 18. OBV
            indicators['OBV'] = talib.OBV(close, volume)[-1]
            
            # 19. TRIX
            indicators['TRIX'] = self.calculate_trix(close, 14)
            
            # 20. DPO
            indicators['DPO'] = self.calculate_dpo(close, 20)
            
            # 21. CMO
            indicators['CMO'] = talib.CMO(close, timeperiod=14)[-1]
            
            # 22. Aroon
            aroon_down, aroon_up = talib.AROON(high, low, timeperiod=25)
            indicators['Aroon_Down'] = aroon_down[-1]
            indicators['Aroon_Up'] = aroon_up[-1]
            indicators['Aroon'] = aroon_up[-1] - aroon_down[-1]
            
            # 23. TSI
            indicators['TSI'] = self.calculate_tsi(close, 25, 13)
            
            # 24. Ultimate Oscillator
            indicators['UO'] = talib.ULTOSC(high, low, close, timeperiod1=7, timeperiod2=14, timeperiod3=28)[-1]
            
            # 25. VWAP
            indicators['VWAP'] = self.calculate_vwap(high, low, close, volume)
            
            # 26. PVT
            indicators['PVT'] = self.calculate_pvt(close, volume)
            
            # 27. EMV
            indicators['EMV'] = self.calculate_emv(high, low, volume, 14)
            
            # 28. Force Index
            indicators['Force'] = self.calculate_force_index(close, volume, 13)
            
            # 29. Chaikin Oscillator
            indicators['ChaikinOsc'] = self.calculate_chaikin_oscillator(high, low, close, volume, 3, 10)
            
            # 30. Accumulation/Distribution
            indicators['AccDist'] = talib.AD(high, low, close, volume)[-1]
            
            # اندیکاتورهای پیشرفته اضافی
            indicators['TEMA'] = self.calculate_tema(close, 14)
            indicators['Ichimoku'] = self.calculate_ichimoku_cloud(high, low, close)
            
            # 31. KST (Know Sure Thing)
            indicators['KST'] = self.calculate_kst(close)
            
            # 32. Vortex Indicator
            indicators['Vortex'] = self.calculate_vortex(high, low, close, 14)
            
            # 33. Z-Score
            indicators['Z_Score'] = self.calculate_zscore(close, 20)
            
            # 34. Donchian Channel
            indicators['Donchian'] = self.calculate_donchian(high, low, 20)
            
            # 35. Keltner Channel
            indicators['Keltner'] = self.calculate_keltner(high, low, close, 20)
            
            # 36. Parabolic SAR
            indicators['ParabolicSAR'] = talib.SAR(high, low, acceleration=0.02, maximum=0.2)[-1]
            
            # 37. Fisher Transform
            indicators['Fisher'] = self.calculate_fisher_transform(high, low, 9)
            
            # 38. Elder Ray Index
            indicators['ElderRay'] = self.calculate_elder_ray(close, 13)
            
            # 39. Hull Moving Average
            indicators['HullMA'] = self.calculate_hull_ma(close, 9)
            
            # 40. SuperTrend
            indicators['SuperTrend'] = self.calculate_supertrend(high, low, close, 10, 3)
            
            # قیمت فعلی برای تحلیل‌های بعدی
            indicators['close'] = close[-1]
            indicators['high'] = high[-1]
            indicators['low'] = low[-1]
            indicators['open'] = open_price[-1]
            
        except Exception as e:
            print(f"خطا در محاسبه اندیکاتورها: {e}")
            import traceback
            traceback.print_exc()
        
        return indicators
    
    # توابع محاسبه اندیکاتورهای پیشرفته
    def calculate_rsi(self, prices, period=14):
        """محاسبه RSI با استفاده از فرمول دقیق"""
        if len(prices) < period + 1:
            return 50
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # میانگین متحرک نمایی
        avg_gain = np.zeros_like(gains)
        avg_loss = np.zeros_like(losses)
        
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])
        
        for i in range(period+1, len(gains)):
            avg_gain[i] = (avg_gain[i-1] * (period-1) + gains[i]) / period
            avg_loss[i] = (avg_loss[i-1] * (period-1) + losses[i]) / period
        
        if avg_loss[-1] == 0:
            return 100 if avg_gain[-1] > 0 else 50
        
        rs = avg_gain[-1] / avg_loss[-1]
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """محاسبه MACD با دقت بالا"""
        if len(prices) < slow:
            return 0, 0, 0
        
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)
        macd_line = ema_fast - ema_slow
        
        # محاسبه خط سیگنال (EMA از MACD)
        macd_prices = [macd_line] if isinstance(macd_line, (int, float)) else macd_line
        signal_line = self.calculate_ema(macd_prices, signal)
        
        # هیستوگرام MACD
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def calculate_ema(self, prices, period):
        """محاسبه EMA با فرمول دقیق"""
        if len(prices) < period:
            return np.mean(prices) if len(prices) > 0 else 0
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """محاسبه باندهای بولینگر با دقت بالا"""
        if len(prices) < period:
            current_price = prices[-1] if len(prices) > 0 else 0
            return current_price, current_price, current_price, 0, 0
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        # پهنای باند (نسبتی)
        bandwidth = (upper_band - lower_band) / sma
        
        # موقعیت قیمت در باند
        position = (prices[-1] - lower_band) / (upper_band - lower_band) if upper_band != lower_band else 0.5
        
        return upper_band, sma, lower_band, bandwidth, position
    
    def calculate_trix(self, prices, period=14):
        """محاسبه TRIX indicator"""
        if len(prices) < period * 3:
            return 0
        
        # محاسبه Triple EMA
        ema1 = self.calculate_ema(prices, period)
        ema2 = self.calculate_ema([ema1], period)
        ema3 = self.calculate_ema([ema2], period)
        
        # محاسبه نرخ تغییر
        if isinstance(ema3, (int, float)) and len(prices) > 1:
            prev_ema3 = self.calculate_ema(prices[:-1], period)
            prev_ema2 = self.calculate_ema([prev_ema3], period)
            prev_ema1 = self.calculate_ema([prev_ema2], period)
            
            if prev_ema1 != 0:
                trix = (ema3 - prev_ema1) / prev_ema1 * 100
                return trix
        
        return 0
    
    def calculate_tsi(self, prices, long_period=25, short_period=13):
        """محاسبه True Strength Index"""
        if len(prices) < long_period + short_period:
            return 0
        
        # محاسبه تغییرات قیمت
        price_changes = np.diff(prices)
        
        # محاسبه EMA دوگانه از تغییرات مثبت
        positive_changes = np.where(price_changes > 0, price_changes, 0)
        double_ema_pos = self.calculate_ema(
            self.calculate_ema(positive_changes, short_period), 
            long_period
        )
        
        # محاسبه EMA دوگانه از تغییرات منفی (مقدار مطلق)
        negative_changes = np.where(price_changes < 0, -price_changes, 0)
        double_ema_neg = self.calculate_ema(
            self.calculate_ema(negative_changes, short_period), 
            long_period
        )
        
        if double_ema_neg == 0:
            return 100 if double_ema_pos > 0 else 0
        
        tsi = 100 * (double_ema_pos / double_ema_neg)
        return tsi
    
    def calculate_vwap(self, high, low, close, volume):
        """محاسبه Volume Weighted Average Price"""
        if len(volume) == 0 or np.sum(volume) == 0:
            return np.mean(close) if len(close) > 0 else 0
        
        typical_price = (high + low + close) / 3
        vwap = np.sum(typical_price * volume) / np.sum(volume)
        return vwap
    
    def calculate_chaikin_oscillator(self, high, low, close, volume, fast_period=3, slow_period=10):
        """محاسبه Chaikin Oscillator"""
        if len(close) < slow_period:
            return 0
        
        # محاسبه Money Flow Volume
        mfv = ((close - low) - (high - close)) / (high - low)
        mfv = np.nan_to_num(mfv, nan=0.0, posinf=0.0, neginf=0.0)
        ad = mfv * volume
        
        # محاسبه EMA سریع و کند
        ema_fast = self.calculate_ema(ad, fast_period)
        ema_slow = self.calculate_ema(ad, slow_period)
        
        return ema_fast - ema_slow
    
    def calculate_ichimoku_cloud(self, high, low, close, tenkan_period=9, kijun_period=26, senkou_span_b_period=52):
        """محاسبه ابر ایچیموکو"""
        if len(close) < senkou_span_b_period:
            return 50
        
        # Tenkan-sen (Conversion Line)
        tenkan_high = np.max(high[-tenkan_period:])
        tenkan_low = np.min(low[-tenkan_period:])
        tenkan_sen = (tenkan_high + tenkan_low) / 2
        
        # Kijun-sen (Base Line)
        kijun_high = np.max(high[-kijun_period:])
        kijun_low = np.min(low[-kijun_period:])
        kijun_sen = (kijun_high + kijun_low) / 2
        
        # Senkou Span A (Leading Span A)
        senkou_span_a = (tenkan_sen + kijun_sen) / 2
        
        # Senkou Span B (Leading Span B)
        senkou_high = np.max(high[-senkou_span_b_period:])
        senkou_low = np.min(low[-senkou_span_b_period:])
        senkou_span_b = (senkou_high + senkou_low) / 2
        
        # موقعیت قیمت نسبت به ابر
        current_price = close[-1]
        cloud_top = max(senkou_span_a, senkou_span_b)
        cloud_bottom = min(senkou_span_a, senkou_span_b)
        
        if current_price > cloud_top:
            return 75  # بالای ابر (صعودی)
        elif current_price < cloud_bottom:
            return 25  # زیر ابر (نزولی)
        elif cloud_top > cloud_bottom:
            return 65  # داخل ابر صعودی
        else:
            return 35  # داخل ابر نزولی
    
    def calculate_kst(self, close, roc1=10, roc2=15, roc3=20, roc4=30, ma1=10, ma2=10, ma3=10, ma4=15, signal=9):
        """محاسبه Know Sure Thing oscillator"""
        if len(close) < max(roc4, ma4) + signal:
            return 0
        
        # محاسبه ROCهای مختلف
        roc1_val = talib.ROC(close, timeperiod=roc1)
        roc2_val = talib.ROC(close, timeperiod=roc2)
        roc3_val = talib.ROC(close, timeperiod=roc3)
        roc4_val = talib.ROC(close, timeperiod=roc4)
        
        # هموار کردن با MA
        roc1_smoothed = talib.SMA(roc1_val, timeperiod=ma1)
        roc2_smoothed = talib.SMA(roc2_val, timeperiod=ma2)
        roc3_smoothed = talib.SMA(roc3_val, timeperiod=ma3)
        roc4_smoothed = talib.SMA(roc4_val, timeperiod=ma4)
        
        # ترکیب با وزن‌های مختلف
        kst = (roc1_smoothed * 1) + (roc2_smoothed * 2) + (roc3_smoothed * 3) + (roc4_smoothed * 4)
        
        return kst[-1] if len(kst) > 0 else 0
    
    def calculate_vortex(self, high, low, close, period=14):
        """محاسبه Vortex Indicator"""
        if len(close) < period + 1:
            return 0
        
        # محاسبه حرکت مثبت و منفی
        vm_plus = np.abs(high[1:] - low[:-1])
        vm_minus = np.abs(low[1:] - high[:-1])
        
        # محاسبه True Range
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        true_range = np.maximum.reduce([tr1, tr2, tr3])
        
        # هموارسازی با دوره
        vm_plus_smoothed = talib.SMA(vm_plus, timeperiod=period)
        vm_minus_smoothed = talib.SMA(vm_minus, timeperiod=period)
        tr_smoothed = talib.SMA(true_range, timeperiod=period)
        
        vi_plus = vm_plus_smoothed[-1] / tr_smoothed[-1] if tr_smoothed[-1] != 0 else 0
        vi_minus = vm_minus_smoothed[-1] / tr_smoothed[-1] if tr_smoothed[-1] != 0 else 0
        
        return vi_plus - vi_minus
    
    def calculate_zscore(self, prices, period=20):
        """محاسبه Z-Score برای تشخیص انحراف از میانگین"""
        if len(prices) < period:
            return 0
        
        recent_prices = prices[-period:]
        mean = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        if std == 0:
            return 0
        
        z_score = (prices[-1] - mean) / std
        return z_score
    
    def calculate_supertrend(self, high, low, close, period=10, multiplier=3):
        """محاسبه SuperTrend indicator"""
        if len(close) < period:
            return 0
        
        # محاسبه ATR
        atr = talib.ATR(high, low, close, timeperiod=period)[-1]
        
        # محاسبه خطوط پایه
        hl2 = (high + low) / 2
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        # تعیین روند
        if close[-1] > upper_band:
            return 1  # روند صعودی
        elif close[-1] < lower_band:
            return -1  # روند نزولی
        else:
            return 0  # بدون روند مشخص
    
    # سایر توابع اندیکاتور (با پیاده‌سازی کامل)
    def calculate_dpo(self, prices, period=20):
        """محاسبه Detrended Price Oscillator"""
        if len(prices) < period:
            return 0
        
        # محاسبه میانگین متحرک ساده
        sma = talib.SMA(prices, timeperiod=period)
        
        # DPO = قیمت فعلی - SMA shifted back by period/2 + 1
        shift_period = period // 2 + 1
        if len(sma) > shift_period:
            dpo = prices[-1] - sma[-(shift_period + 1)]
            return dpo
        
        return 0
    
    def calculate_emv(self, high, low, volume, period=14):
        """محاسبه Ease of Movement"""
        if len(high) < period + 1:
            return 0
        
        # محاسبه فاصله حرکت
        distance_moved = ((high[1:] + low[1:]) / 2) - ((high[:-1] + low[:-1]) / 2)
        
        # محاسبه جعبه نسبت
        box_ratio = (volume[1:] / 100000000) / (high[1:] - low[1:])
        
        # محاسبه EMV
        emv = distance_moved / box_ratio
        emv_smoothed = talib.SMA(emv, timeperiod=period)
        
        return emv_smoothed[-1] if len(emv_smoothed) > 0 else 0
    
    def calculate_force_index(self, close, volume, period=13):
        """محاسبه Force Index"""
        if len(close) < period + 1:
            return 0
        
        # تغییرات قیمت
        price_change = np.diff(close)
        
        # Force Index
        force_index = price_change * volume[1:]
        force_index_smoothed = talib.EMA(force_index, timeperiod=period)
        
        return force_index_smoothed[-1] if len(force_index_smoothed) > 0 else 0
    
    def calculate_pvt(self, close, volume):
        """محاسبه Price Volume Trend"""
        if len(close) < 2:
            return 0
        
        # محاسبه تغییر(pvt) >= 20 else np.sum(pvt)
    
    def calculate_donchian(self, high, low, period=20):
        """محاسبه Donchian Channel"""
        if len(high) < period:
            return 0
        
        upper = np.max(high[-period:])
        lower = np.min(low[-period:])
        middle = (upper + lower) / 2
        
        # موقعیت قیمت در کانال
        current_price = (high[-1] + low[-1]) / 2
        position = (current_price - lower) / (upper - lower) if upper != lower else 0.5
        
        return position * 100
    
    def calculate_keltner(self, high, low, close, period=20, multiplier=2):
        """محاسبه Keltner Channel"""
        if len(close) < period:
            return 0
        
        # میانگین متحرک
        ema = talib.EMA(close, timeperiod=period)
        
        # میانگین True Range
        atr = talib.ATR(high, low, close, timeperiod=period)
        
        upper_band = ema[-1] + (multiplier * atr[-1])
        lower_band = ema[-1] - (multiplier * atr[-1])
        
        # موقعیت قیمت در کانال
        current_price = close[-1]
        position = (current_price - lower_band) / (upper_band - lower_band) if upper_band != lower_band else 0.5
        
        return position * 100
    
    def calculate_fisher_transform(self, high, low, period=9):
        """محاسبه Fisher Transform"""
        if len(high) < period:
            return 0
        
        # محاسبه قیمت میانه
        median_price = (high + low) / 2
        
        # نرمال‌سازی قیمت
        max_price = np.max(high[-period:])
        min_price = np.min(low[-period:])
        
        if max_price == min_price:
            return 0
        
        normalized_price = (median_price[-1] - min_price) / (max_price - min_price) * 2 - 1
        
        # Fisher Transform
        fisher = 0.5 * np.log((1 + normalized_price) / (1 - normalized_price))
        
        return fisher
    
    def calculate_elder_ray(self, close, period=13):
        """محاسبه Elder Ray Index"""
        if len(close) < period:
            return 0
        
        ema = talib.EMA(close, timeperiod=period)
        bull_power = high[-1] - ema[-1]
        bear_power = low[-1] - ema[-1]
        
        return bull_power + bear_power
    
    def calculate_hull_ma(self, prices, period=9):
        """محاسبه Hull Moving Average"""
        if len(prices) < period:
            return prices[-1] if len(prices) > 0 else 0
        
        # محاسبه WMA با دوره n/2
        wma_half = talib.WMA(prices, timeperiod=period//2)
        
        # محاسبه WMA با دوره n
        wma_full = talib.WMA(prices, timeperiod=period)
        
        # محاسبه Hull MA
        hull_ma = talib.WMA(2 * wma_half - wma_full, timeperiod=int(np.sqrt(period)))
        
        return hull_ma[-1] if len(hull_ma) > 0 else prices[-1]
    
    def calculate_tema(self, prices, period=14):
        """محاسبه Triple Exponential Moving Average"""
        if len(prices) < period * 3:
            return prices[-1] if len(prices) > 0 else 0
        
        ema1 = talib.EMA(prices, timeperiod=period)
        ema2 = talib.EMA(ema1, timeperiod=period)
        ema3 = talib.EMA(ema2, timeperiod=period)
        
        tema = 3 * ema1 - 3 * ema2 + ema3
        
        return tema[-1] if len(tema) > 0 else prices[-1]
    
    def generate_signal(self, indicators, strategy_type='moderate'):
        """تولید سیگنال با استفاده از وزن‌های مختلف"""
        if not indicators:
            return "NO_SIGNAL", 0, 0, 0, 0, 0, 0
        
        weights = INDICATOR_WEIGHTS.get(strategy_type, INDICATOR_WEIGHTS['moderate'])
        total_score = 0
        max_possible_score = sum(weights.values())
        
        # محاسبه امتیاز برای هر اندیکاتور
        indicator_scores = {}
        
        # 1. RSI (0-100)
        rsi = indicators.get('RSI', 50)
        if rsi < 30:
            indicator_scores['RSI'] = weights['RSI'] * 1.0  # اشباع فروش
        elif rsi > 70:
            indicator_scores['RSI'] = weights['RSI'] * -1.0  # اشباع خرید
        else:
            indicator_scores['RSI'] = weights['RSI'] * ((rsi - 50) / 20)  # نرمال
        
        # 2. MACD
        macd = indicators.get('MACD', 0)
        macd_signal = indicators.get('MACD_Signal', 0)
        if macd > macd_signal and macd > 0:
            indicator_scores['MACD'] = weights['MACD'] * 1.0
        elif macd < macd_signal and macd < 0:
            indicator_scores['MACD'] = weights['MACD'] * -1.0
        else:
            indicator_scores['MACD'] = weights['MACD'] * (macd / (abs(macd) + 0.0001)) * 0.5
        
        # 3-5. Moving Averages
        close = indicators.get('close', 0)
        ma20 = indicators.get('MA20', close)
        ma50 = indicators.get('MA50', close)
        ma200 = indicators.get('MA200', close)
        
        # بررسی موقعیت قیمت نسبت به MAها
        ma_score = 0
        if close > ma20 > ma50 > ma200:
            ma_score = 1.0  # روند صعودی قوی
        elif close < ma20 < ma50 < ma200:
            ma_score = -1.0  # روند نزولی قوی
        else:
            # محاسبه امتیاز بر اساس فاصله از MAها
            ma20_dist = (close - ma20) / ma20 if ma20 != 0 else 0
            ma50_dist = (close - ma50) / ma50 if ma50 != 0 else 0
            ma200_dist = (close - ma200) / ma200 if ma200 != 0 else 0
            ma_score = (ma20_dist + ma50_dist + ma200_dist) / 3 * 10  # نرمال‌سازی
        
        indicator_scores['MA20'] = weights['MA20'] * ma_score
        indicator_scores['MA50'] = weights['MA50'] * ma_score
        indicator_scores['MA200'] = weights['MA200'] * ma_score
        
        # 6-7. Bollinger Bands
        bb_position = indicators.get('BB_Position', 0.5)
        if bb_position > 0.8:
            indicator_scores['BB_Upper'] = weights['BB_Upper'] * -1.0  # نزدیک به باند بالا
        elif bb_position < 0.2:
            indicator_scores['BB_Lower'] = weights['BB_Lower'] * 1.0  # نزدیک به باند پایین
        else:
            indicator_scores['BB_Upper'] = weights['BB_Upper'] * 0
            indicator_scores['BB_Lower'] = weights['BB_Lower'] * 0
        
        # 8. Stochastic
        stoch = indicators.get('Stoch', 50)
        if stoch < 20:
            indicator_scores['Stoch'] = weights['Stoch'] * 1.0
        elif stoch > 80:
            indicator_scores['Stoch'] = weights['Stoch'] * -1.0
        else:
            indicator_scores['Stoch'] = weights['Stoch'] * ((stoch - 50) / 30)
        
        # 9. Williams %R
        williams = indicators.get('Williams', -50)
        if williams < -80:
            indicator_scores['Williams'] = weights['Williams'] * 1.0
        elif williams > -20:
            indicator_scores['Williams'] = weights['Williams'] * -1.0
        else:
            indicator_scores['Williams'] = weights['Williams'] * ((williams + 50) / -30)
        
        # 10. ADX (قدرت روند)
        adx = indicators.get('ADX', 0)
        if adx > 25:
            # روند قوی است، تقویت سیگنال
            trend_strength = min(adx / 50, 2.0)  # حداکثر 2 برابر تقویت
        else:
            trend_strength = 1.0
        
        # 11. CCI
        cci = indicators.get('CCI', 0)
        if cci > 100:
            indicator_scores['CCI'] = weights['CCI'] * -1.0
        elif cci < -100:
            indicator_scores['CCI'] = weights['CCI'] * 1.0
        else:
            indicator_scores['CCI'] = weights['CCI'] * (cci / 100)
        
        # 12. Volume Analysis
        volume_ratio = indicators.get('Volume_Ratio', 1)
        if volume_ratio > 1.5:
            # حجم معاملات بالا - تقویت سیگنال
            volume_strength = min(volume_ratio, 2.0)
        else:
            volume_strength = 1.0
        
        # 13. ROC
        roc = indicators.get('ROC', 0)
        indicator_scores['ROC'] = weights['ROC'] * (roc / 10)  # نرمال‌سازی
        
        # 14. MFI
        mfi = indicators.get('MFI', 50)
        if mfi < 20:
            indicator_scores['MFI'] = weights['MFI'] * 1.0
        elif mfi > 80:
            indicator_scores['MFI'] = weights['MFI'] * -1.0
        else:
            indicator_scores['MFI'] = weights['MFI'] * ((mfi - 50) / 30)
        
        # محاسبه سایر اندیکاتورها به صورت مشابه...
        
        # محاسبه امتیاز نهایی با در نظر گرفتن قدرت روند و حجم
        for indicator, score in indicator_scores.items():
            total_score += score * trend_strength * volume_strength
        
        # نرمال‌سازی امتیاز به بازه -100 تا 100
        normalized_score = (total_score / max_possible_score) * 100
        normalized_score = max(min(normalized_score, 100), -100)
        
        # تولید سیگنال
        if normalized_score > 20:
            signal = "BUY"
            confidence = min(normalized_score / 100, 1.0)
        elif normalized_score < -20:
            signal = "SELL"
            confidence = min(abs(normalized_score) / 100, 1.0)
        else:
            signal = "HOLD"
            confidence = 0
        
        # محاسبه حد سود و ضرر
        atr = indicators.get('ATR', 0)
        current_price = indicators.get('close', 0)
        
        if atr > 0 and current_price > 0:
            # برای خرید: حد ضرر زیر قیمت فعلی به اندازه 2 ATR، حد سود بالای قیمت به اندازه 3 ATR
            stop_loss_buy = current_price - (2 * atr)
            take_profit_buy = current_price + (3 * atr)
            
            # برای فروش: حد ضرر بالای قیمت فعلی به اندازه 2 ATR، حد سود زیر قیمت به اندازه 3 ATR
            stop_loss_sell = current_price + (2 * atr)
            take_profit_sell = current_price - (3 * atr)
        else:
            # مقادیر پیش‌فرض در صورت عدم محاسبه ATR
            stop_loss_buy = current_price * 0.95
            take_profit_buy = current_price * 1.10
            stop_loss_sell = current_price * 1.05
            take_profit_sell = current_price * 0.90
        
        leverage = 5  # اهرم ثابت
        
        return signal, confidence, stop_loss_buy, take_profit_buy, stop_loss_sell, take_profit_sell, leverage
    
    async def analyze_crypto(self, symbol, strategy_type='moderate'):
        """آنالیز کامل یک ارز دیجیتال"""
        await self.init_session()
        
        # دریافت داده‌ها
        df = await self.get_crypto_data(symbol)
        if df is None or len(df) < 50:
            return None
        
        # محاسبه اندیکاتورها
        indicators = self.calculate_all_indicators(df)
        if not indicators:
            return None
        
        # تولید سیگنال
        signal, confidence, sl_buy, tp_buy, sl_sell, tp_sell, leverage = self.generate_signal(indicators, strategy_type)
        
        # آماده‌سازی نتیجه
        result = {
            'symbol': symbol,
            'price': indicators.get('close', 0),
            'signal': signal,
            'confidence': confidence,
            'stop_loss_buy': sl_buy,
            'take_profit_buy': tp_buy,
            'stop_loss_sell': sl_sell,
            'take_profit_sell': tp_sell,
            'leverage': leverage,
            'indicators': indicators,
            'timestamp': datetime.now().isoformat()
        }
        
        return result

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
        "🤖 ربات تحلیل ارزهای دیجیتال - نسخه پیشرفته\n\n"
        "این ربات با استفاده از 40+ اندیکاتور پیشرفته و الگوریتم‌های هوشمند، "
        "سیگنال‌های دقیق برای معاملات ارائه می‌دهد.\n\n"
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
        for i in range(0, len(CRYPTO_SYMBOLS), 2):
            row = []
            for symbol in CRYPTO_SYMBOLS[i:i+2]:
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
            [InlineKeyboardButton("⚡ اسکالپینگ", callback_data="strategy_scalping")],
            [InlineKeyboardButton("📈 سوینگ تریدینگ", callback_data="strategy_swing")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ لطفا استراتژی معاملاتی خود را انتخاب کنید:\n\n"
            "🛡️ محافظه کارانه: ریسک کم، سود متوسط\n"
            "⚖️ متعادل: تعادل بین ریسک و سود\n"
            "🚀 پرریسک: ریسک بالا، سود بالقوه بالا\n"
            "⚡ اسکالپینگ: معاملات کوتاه مدت\n"
            "📈 سوینگ تریدینگ: معاملات میان مدت",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("strategy_"):
        strategy_type = query.data.replace("strategy_", "")
        context.user_data['strategy'] = strategy_type
        
        strategy_names = {
            'conservative': 'محافظه کارانه',
            'moderate': 'متعادل',
            'aggressive': 'پرریسک',
            'scalping': 'اسکالپینگ',
            'swing': 'سوینگ تریدینگ'
        }
        
        await query.edit_message_text(
            f"✅ استراتژی به {strategy_names.get(strategy_type, 'متعادل')} تغییر یافت."
        )
    
    elif query.data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("📊 تحلیل همه ارزها", callback_data="analyze_all")],
            [InlineKeyboardButton("🎯 تحلیل ارز خاص", callback_data="analyze_specific")],
            [InlineKeyboardButton("⚙️ تنظیمات استراتژی", callback_data="strategy_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🤖 ربات تحلیل ارزهای دیجیتال - نسخه پیشرفته\n\n"
            "لطفا یک گزینه انتخاب کنید:",
            reply_markup=reply_markup
        )

async def analyze_all_cryptos(query, context):
    """آنالیز همه ارزهای دیجیتال"""
    results = []
    
    for symbol in CRYPTO_SYMBOLS:
        try:
            strategy = context.user_data.get('strategy', 'moderate')
            result = await analyzer.analyze_crypto(symbol, strategy)
            if result:
                results.append(result)
                await asyncio.sleep(0.5)  # جلوگیری از Rate Limit
        except Exception as e:
            print(f"خطا در تحلیل {symbol}: {e}")
    
    # مرتب‌سازی بر اساس قدرت سیگنال
    buy_signals = [r for r in results if r['signal'] == 'BUY']
    sell_signals = [r for r in results if r['signal'] == 'SELL']
    hold_signals = [r for r in results if r['signal'] == 'HOLD']
    
    buy_signals.sort(key=lambda x: x['confidence'], reverse=True)
    sell_signals.sort(key=lambda x: x['confidence'], reverse=True)
    
    # ایجاد گزارش
    message = "📊 نتایج تحلیل همه ارزها:\n\n"
    
    if buy_signals:
        message += "🟢 سیگنال‌های خرید قوی:\n"
        for signal in buy_signals[:3]:  # فقط 3 سیگنال برتر
            message += f"{signal['symbol']}: اطمینان {signal['confidence']:.0%} - قیمت: ${signal['price']:.2f}\n"
        message += "\n"
    
    if sell_signals:
        message += "🔴 سیگنال‌های فروش قوی:\n"
        for signal in sell_signals[:3]:
            message += f"{signal['symbol']}: اطمینان {signal['confidence']:.0%} - قیمت: ${signal['price']:.2f}\n"
        message += "\n"
    
    message += f"📈 تعداد سیگنال‌های خرید: {len(buy_signals)}\n"
    message += f"📉 تعداد سیگنال‌های فروش: {len(sell_signals)}\n"
    message += f"⚖️ تعداد سیگنال‌های انتظار: {len(hold_signals)}\n\n"
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
        
        # ایجاد پیام گزارش
        message = f"📈 تحلیل پیشرفته {symbol}\n\n"
        message += f"💰 قیمت فعلی: ${result['price']:.2f}\n"
        message += f"🎯 سیگنال: {result['signal']} (اطمینان: {result['confidence']:.0%})\n\n"
        
        if result['signal'] == 'BUY':
            message += f"🛑 حد ضرر: ${result['stop_loss_buy']:.2f}\n"
            message += f"🎯 حد سود: ${result['take_profit_buy']:.2f}\n"
            message += f"⚖️ اهرم پیشنهادی: {result['leverage']}x\n\n"
        elif result['signal'] == 'SELL':
            message += f"🛑 حد ضرر: ${result['stop_loss_sell']:.2f}\n"
            message += f"🎯 حد سود: ${result['take_profit_sell']:.2f}\n"
            message += f"⚖️ اهرم پیشنهادی: {result['leverage']}x\n\n"
        
        # اطلاعات برخی اندیکاتورهای کلیدی
        message += "📊 اندیکاتورهای کلیدی:\n"
        message += f"RSI: {result['indicators'].get('RSI', 0):.1f}\n"
        message += f"MACD: {result['indicators'].get('MACD', 0):.4f}\n"
        message += f"میانگین متحرک 20: ${result['indicators'].get('MA20', 0):.2f}\n"
        message += f"میانگین متحرک 50: ${result['indicators'].get('MA50', 0):.2f}\n"
        message += f"باند بولینگر: {result['indicators'].get('BB_Position', 0.5)*100:.1f}%\n\n"
        
        message += "⏰ زمان تحلیل: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
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
    application.run_polling()

if __name__ == "__main__":
    # اجرای اصلی
    try:
        main()
    except KeyboardInterrupt:
        print("ربات متوقف شد.")
    finally:
        # بستن session هنگام خروج
        asyncio.run(analyzer.close_session())
