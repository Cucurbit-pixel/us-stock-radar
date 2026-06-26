import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. 網頁基本設定
st.set_page_config(page_title="大數據量化掃描器", layout="wide", initial_sidebar_state="expanded")

# 2. 安全調用 Streamlit Secrets 設定檔
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error(f"❌ 錯誤：找不到設定中的 Alpaca 金鑰，請前往 Streamlit Settings -> Secrets 設定好金鑰。")
    st.stop()

# 3. 在 側邊欄 (Sidebar) 設定
st.sidebar.title("🤖 雷達導航中心")
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 量化條件篩選")

market_stage_filter = st.sidebar.selectbox(
    "選擇 Stan Weinstein 階段",
    ["全部", "第一階段 (整理期)", "第二階段 (強勢期)", "第三階段 (派發期)", "第四階段 (弱勢期)", "其他/無明顯狀態"]
)

rs_score = st.sidebar.slider("最低相對強度 (RS) 分數", min_value=10, max_value=99, value=70)
st.sidebar.caption("數據來源：Alpaca API 大數據全自動對接")

# 4. 全自動數據 (API) 呼叫函數
@st.cache_data
def fetch_market_data(tickers):
    data_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
    }
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    params = {
        "symbols": ",".join(tickers),
        "timeframe": "1Day",
        "start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "adjustment": "all",
        "feed": "iex" 
    }
    
    response = requests.get(data_url, headers=headers, params=params)
    
    if response.status_code != 200:
        st.error(f"❌ 數據提取失敗: {response.status_code}")
        return None
        
    return response.json().get("bars", {})

# 5. 執行大數據掃描與量化計算
with st.spinner("🤖 正在處理數據..."):
    WATCH_LIST = ["NVDA", "AMD", "SMCI", "AMZN", "AAPL", "MSFT", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX"]
    all_bars = fetch_market_data(WATCH_LIST)

if all_bars:
    processed_results = []
    
    for ticker, bars in all_bars.items():
        if len(bars) < 150: # 需要至少 150 日數據
            continue
            
        df = pd.DataFrame(bars)
        df['close'] = df['c']
        
        # 計算 150 日線
        df['ma150'] = df['close'].rolling(window=150).mean()
        
        # 【修正核心】計算半年 (約126個交易日) 漲跌幅
        if len(df) >= 126:
            price_now = df['close'].iloc[-1]
            price_6mo_ago = df['close'].iloc[-126]
            half_year_perf = ((price_now - price_6mo_ago) / price_6mo_ago) * 100
        else:
            half_year_perf = 0
            
        # 計算 RS 評分
        rs_rating = min(int(50 + half_year_perf), 100)
        
        processed_results.append({
            "ticker": ticker,
            "price": df['close'].iloc[-1],
            "ma150": df['ma150'].iloc[-1],
            "rs": rs_rating
        })

    report_df = pd.DataFrame(processed_results)
    if not report_df.empty:
        st.success("✅ 數據擷取成功！")
        st.dataframe(report_df)
    else:
        st.warning("⚠️ 沒有符合條件數據。")
