import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. 網頁設定
st.set_page_config(page_title="臨玖量化雷達", layout="wide")

# 2. 安全調用 Secrets
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error("❌ 請在 Streamlit Secrets 設定 Alpaca 金鑰。")
    st.stop()

# 3. 行業分類映射表 (GICS 簡化版)
SECTOR_MAP = {
    "NVDA": "半導體", "AMD": "半導體", "SMCI": "硬體設備", "AVGO": "半導體",
    "AMZN": "消費服務", "AAPL": "科技硬體", "MSFT": "軟體服務", "GOOGL": "互動媒體",
    "META": "互動媒體", "TSLA": "汽車", "COST": "必需消費", "NFLX": "娛樂"
}

# 輔助函數：火箭等級
def get_rocket_emoji(rs):
    if rs >= 85: return "🚀🚀🚀"
    if rs >= 70: return "🚀🚀"
    return "🚀"

# 4. API 呼叫函數
@st.cache_data(ttl=3600)
def fetch_market_data(tickers):
    data_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY}
    params = {
        "symbols": ",".join(tickers),
        "timeframe": "1Day",
        "start": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "feed": "iex",
        "adjustment": "all"
    }
    response = requests.get(data_url, headers=headers, params=params)
    return response.json().get("bars", {})

# 5. 主程式
st.title("📈 臨玖 - 全自動量化篩選強勢股")

# 增加股票列表
WATCH_LIST = ["NVDA", "AMD", "SMCI", "AMZN", "AAPL", "MSFT", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", "MSI", "INTU", "V"]
all_bars = fetch_market_data(WATCH_LIST)

if all_bars:
    processed_results = []
    for ticker, bars in all_bars.items():
        if len(bars) < 150: continue
        df = pd.DataFrame(bars)
        df['close'] = df['c']
        
        # 計算指標
        current_price = df['close'].iloc[-1]
        ma150 = df['close'].rolling(window=150).mean().iloc[-1]
        half_year_perf = ((current_price - df['close'].iloc[-126]) / df['close'].iloc[-126]) * 100
        rs_rating = min(int(50 + half_year_perf), 99)
        
        processed_results.append({
            "股票": ticker,
            "行業": SECTOR_MAP.get(ticker, "其他"),
            "現價 ($)": round(current_price, 2),
            "RS 分數": rs_rating,
            "動能": get_rocket_emoji(rs_rating)
        })

    report_df = pd.DataFrame(processed_results).sort_values(by="RS 分數", ascending=False)
    st.dataframe(report_df, use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ 數據獲取中，請稍候...")
