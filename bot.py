import asyncio
import logging
import aiohttp
import json
from datetime import datetime
import pandas as pd
import numpy as np
import pandas_ta as ta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# تنظیمات
TELEGRAM_BOT_TOKEN = "8052349235:AAFSaJmYpl359BKrJTWC8O-u-dI9r2olEOQ"
ALPHA_VANTAGE_API = "uSuLsH9hvMCRLyvw4WzUZiGB"

# لیست ارزهای مورد نظر
CRYPTO_SYMBOLS = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE', 'MATIC', 'DOT', 'AVAX']

# وزن‌های اندیکاتورها
INDICATOR_WEIGHTS = {
    'conservative': {'RSI': 20, 'MACD': 15, 'MA20': 25, 'MA50': 30, 'BB': 10},
    'moderate': {'RSI': 25, 'MACD': 20, 'MA20': 20, 'MA50': 20, 'BB': 15},
    'aggressive': {'RSI': 30, 'MACD': 25, 'MA20': 15, 'MA50': 10, 'BB': 20}
}

class SimpleCryptoAnalyzer:
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
            df_data = []
            
            for date, values in list(time_series.items())[:100]:
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
            return df.sort_values('date').reset_index(drop=True)
            
        except Exception as e:
            print(f"خطا در دریافت داده‌های {symbol}: {e}")
            return None
    
    def calculate_indicators(self, df):
        """محاسبه اندیکاتورهای اصلی با pandas-ta"""
        if df is None or len(df) < 50:
            return {}
        
        try:
            close = df['close'].values
            indicators = {}
            
            # RSI
            rsi = ta.rsi(df['close'], length=14)
            indicators['RSI'] = rsi.iloc[-1] if not rsi.empty else 50
            
            # MACD
            macd = ta.macd(df['close'])
            indicators['MACD'] = macd['MACD_12_26_9'].iloc[-1] if not macd.empty else 0
            
            # Moving Averages
            indicators['MA20'] = ta.sma(df['close'], length=20).iloc[-1]
            indicators['MA50'] = ta.sma(df['close'], length=50).iloc[-1]
            
            # Bollinger Bands
            bb = ta.bbands(df['close'], length=20)
            indicators['BB_Upper'] = bb['BBU_20_2.0'].iloc[-1]
            indicators['BB_Lower'] = bb['BBL_20_2.0'].iloc[-1]
            indicators['BB_Middle'] = bb['BBM_20_2.0'].iloc[-1]
            
            # Stochastic
            stoch = ta.stoch(df['high'], df['low'], df['close'])
            indicators['Stoch'] = stoch['STOCHk_14_3_3'].iloc[-1] if not stoch.empty else 50
            
            # Volume
            indicators['Volume'] = df['volume'].iloc[-1]
            
            # قیمت فعلی
            indicators['close'] = close[-1]
            
            return indicators
            
        except Exception as e:
            print(f"خطا در محاسبه اندیکاتورها: {e}")
            return {}
    
    def generate_signal(self, indicators, strategy_type='moderate'):
        """تولید سیگنال معاملاتی"""
        if not indicators:
            return "HOLD", 0.5, 0, 0, 0, 0, 3
        
        weights = INDICATOR_WEIGHTS.get(strategy_type, INDICATOR_WEIGHTS['moderate'])
        total_score = 0
        max_score = sum(weights.values())
        
        # تحلیل RSI
        rsi = indicators.get('RSI', 50)
        if rsi < 30:
            total_score += weights['RSI'] * 1.0
        elif rsi > 70:
            total_score -= weights['RSI'] * 1.0
        
        # تحلیل MACD
        macd = indicators.get('MACD', 0)
        if macd > 0:
            total_score += weights['MACD'] * 0.8
        else:
            total_score -= weights['MACD'] * 0.8
        
        # تحلیل Moving Averages
        close = indicators.get('close', 0)
        ma20 = indicators.get('MA20', close)
        ma50 = indicators.get('MA50', close)
        
        if close > ma20 > ma50:
            total_score += (weights['MA20'] + weights['MA50']) * 0.7
        elif close < ma20 < ma50:
            total_score -= (weights['MA20'] + weights['MA50']) * 0.7
        
        # تحلیل Bollinger Bands
        bb_position = (close - indicators.get('BB_Lower', close)) / (
            indicators.get('BB_Upper', close*1.1) - indicators.get('BB_Lower', close*0.9) + 0.0001)
        
        if bb_position < 0.2:
            total_score += weights['BB'] * 0.9
        elif bb_position > 0.8:
            total_score -= weights['BB'] * 0.9
        
        # نرمال‌سازی امتیاز
        normalized_score = total_score / max_score
        
        # تولید سیگنال
        if normalized_score > 0.2:
            signal = "BUY"
            confidence = min(normalized_score, 0.95)
            stop_loss = close * 0.95
            take_profit = close * 1.10
            leverage = 5
        elif normalized_score < -0.2:
            signal = "SELL"
            confidence = min(abs(normalized_score), 0.95)
            stop_loss = close * 1.05
            take_profit = close * 0.90
            leverage = 5
        else:
            signal = "HOLD"
            confidence = 0.5
            stop_loss = 0
            take_profit = 0
            leverage = 1
        
        return signal, confidence, stop_loss, take_profit, leverage
    
    async def analyze_crypto(self, symbol, strategy_type='moderate'):
        """آنالیز کامل یک ارز"""
        await self.init_session()
        
        df = await self.get_crypto_data(symbol)
        if df is None or len(df) < 20:
            return None
        
        indicators = self.calculate_indicators(df)
        if not indicators:
            return None
        
        signal, confidence, sl, tp, leverage = self.generate_signal(indicators, strategy_type)
        
        return {
            'symbol': symbol,
            'price': indicators.get('close', 0),
            'signal': signal,
            'confidence': confidence,
            'stop_loss': sl,
            'take_profit': tp,
            'leverage': leverage,
            'timestamp': datetime.now().isoformat()
        }

# ایجاد ربات تلگرام
analyzer = SimpleCryptoAnalyzer()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 تحلیل همه ارزها", callback_data="analyze_all")],
        [InlineKeyboardButton("🎯 تحلیل ارز خاص", callback_data="analyze_specific")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 ربات تحلیل ارزهای دیجیتال\n\nلطفا یک گزینه انتخاب کنید:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "analyze_all":
        await analyze_all_cryptos(query)
    elif query.data == "analyze_specific":
        await show_crypto_list(query)

async def analyze_all_cryptos(query):
    await query.edit_message_text("⏳ در حال تحلیل...")
    
    results = []
    for symbol in CRYPTO_SYMBOLS[:5]:  # فقط 5 ارز برای تست
        try:
            result = await analyzer.analyze_crypto(symbol)
            if result:
                results.append(result)
        except:
            continue
    
    message = "📊 نتایج تحلیل:\n\n"
    for result in results:
        emoji = "🟢" if result['signal'] == 'BUY' else "🔴" if result['signal'] == 'SELL' else "⚪"
        message += f"{emoji} {result['symbol']}: {result['signal']} ({result['confidence']:.0%})\n"
    
    await query.edit_message_text(message)

async def show_crypto_list(query):
    keyboard = []
    for symbol in CRYPTO_SYMBOLS:
        keyboard.append([InlineKeyboardButton(symbol, callback_data=f"crypto_{symbol}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🔍 انتخاب ارز:", reply_markup=reply_markup)

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 ربات فعال شد!")
    application.run_polling()

if __name__ == "__main__":
    main()
