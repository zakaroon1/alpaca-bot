import alpaca_trade_api as tradeapi
import pandas as pd
from ta.trend import EMAIndicator, MACD
import time
from datetime import datetime

# إعداد الاتصال بـ Alpaca
API_KEY = "AKO6DU6L0A1GZ1A5O41U"
SECRET_KEY = "yQdAkpoj6reThfoLegVyN4iGlm4qmg4PR44exdva"
BASE_URL = "https://api.alpaca.markets"
api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')

qty = 1
entry_prices = {}  # لتخزين سعر الشراء لكل سهم

def get_all_stocks():
    assets = api.list_assets(status='active', asset_class='us_equity')
    tradable_symbols = [asset.symbol for asset in assets if asset.tradable]
    return tradable_symbols

def get_historical_data(symbol):
    try:
        bars = api.get_bars(symbol, "15Min", limit=50).df
        if len(bars) < 20:
            return None
        return bars
    except Exception as e:
        print(f"❌ خطأ في جلب بيانات {symbol}: {e}")
        return None

def calculate_indicators(df):
    volume = df['volume'].iloc[-1]
    highest_volume = df['volume'].iloc[-21:-1].max()

    macd = MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
    macdh = macd.macd_diff()
    macdh_current = macdh.iloc[-1]
    macdh_previous = macdh.iloc[-2]

    ema7 = EMAIndicator(close=df['close'], window=7).ema_indicator()
    ema7_current = ema7.iloc[-1]
    close_current = df['close'].iloc[-1]

    return volume, highest_volume, macdh_current, macdh_previous, close_current, ema7_current

def trading_strategy():
    print("📦 جلب قائمة الأسهم...")
    symbols = get_all_stocks()
    print(f"✅ عدد الأسهم المتاحة: {len(symbols)}")

    while True:
        try:
            now = datetime.now()
            if now.hour < 13 or now.hour > 20:
                print(f"🔒 السوق مغلق! الساعة الآن {now.strftime('%H:%M:%S')}")
                time.sleep(300)
                continue

            account = api.get_account()
            buying_power = float(account.buying_power)
            print(f"💰 الرصيد المتاح: ${buying_power:.2f}")

            positions = {p.symbol: float(p.qty) for p in api.list_positions()}

            for symbol in symbols:
                df = get_historical_data(symbol)
                if df is None:
                    continue

                volume, highest_volume, macdh_current, macdh_previous, close_current, ema7_current = calculate_indicators(df)

                condition_buy = volume > highest_volume and macdh_current > macdh_previous and close_current > ema7_current
                unrealized_profit = 0
                entry_price = entry_prices.get(symbol)

                # حساب نسبة الربح/الخسارة
                if entry_price:
                    change_pct = ((close_current - entry_price) / entry_price) * 100
                else:
                    change_pct = 0

                condition_sell = (
                    (volume > highest_volume and macdh_current < macdh_previous and close_current < ema7_current)
                    or (entry_price and (change_pct >= 1 or change_pct <= -2))
                )

                if condition_buy and symbol not in positions:
                    if buying_power >= (close_current * qty):
                        api.submit_order(
                            symbol=symbol,
                            qty=qty,
                            side='buy',
                            type='market',
                            time_in_force='gtc'
                        )
                        entry_prices[symbol] = close_current  # حفظ سعر الدخول
                        print(f"✅ شراء {qty} سهم من {symbol} بسعر ${close_current:.2f}")
                        buying_power -= close_current * qty
                    else:
                        print(f"❌ لا يوجد رصيد كافي لشراء {symbol}")

                elif condition_sell and symbol in positions and positions[symbol] >= qty:
                    api.submit_order(
                        symbol=symbol,
                        qty=qty,
                        side='sell',
                        type='market',
                        time_in_force='gtc'
                    )
                    print(f"✅ بيع {qty} سهم من {symbol} بسعر ${close_current:.2f} | نسبة التغير: {change_pct:.2f}%")
                    entry_prices.pop(symbol, None)  # حذف السعر بعد البيع

                else:
                    print(f"🔍 {symbol}: لا توجد فرصة تداول حالياً")

            print("⏳ الانتظار دقيقة واحدة قبل التشييك مرة ثانية...")
            time.sleep(60)

        except Exception as e:
            print(f"⚠️ خطأ عام: {e}")
            time.sleep(60)

if __name__ == "__main__":
    trading_strategy()
