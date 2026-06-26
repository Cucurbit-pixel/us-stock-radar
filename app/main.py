import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="臨玖 - 量化交易終端", layout="wide")

# 1. 核心邏輯：快速讀取市場數據
@st.cache_data(ttl=3600)
def get_market_data(tickers):
    data_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {"APCA-API-KEY-ID": st.secrets["ALPACA_API_KEY"], "APCA-API-SECRET-KEY": st.secrets["ALPACA_SECRET_KEY"]}
    
    all_results = []
    chunk_size = 100
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i+chunk_size]
        params = {"symbols": ",".join(chunk), "timeframe": "1Day", "feed": "iex", "adjustment": "all"}
        try:
            resp = requests.get(data_url, headers=headers, params=params)
            if resp.status_code == 200:
                for ticker, bars in resp.json().get("bars", {}).items():
                    if len(bars) >= 150:
                        df = pd.DataFrame(bars)
                        price = df['c'].iloc[-1]
                        perf = ((price - df['c'].iloc[-126]) / df['c'].iloc[-126]) * 100
                        rs = min(max(int(50 + perf), 10), 99)
                        all_results.append({
                            "股票代號": ticker, "RS 分數": rs, "現價": round(price, 2), "動能": "🚀" * (rs // 30 + 1)
                        })
        except: continue
        time.sleep(0.1)
    return pd.DataFrame(all_results)

# 2. 側邊欄介面
st.sidebar.title("臨玖量化雷達")
search = st.sidebar.text_input("搜尋代碼 (如 NVDA)", "").upper()
rs_limit = st.sidebar.slider("RS 分數門檻", 10, 99, 80)

# 3. 主頁面顯示
st.title("📈 強勢股篩選列表")

# 假設你已經獲取了全美股代碼 (all_tickers)
# master_df = get_market_data(all_tickers) 

if 'master_df' in locals():
    # 強力篩選邏輯
    filtered = master_df[master_df['RS 分數'] >= rs_limit].sort_values("RS 分數", ascending=False)
    
    # 使用你慣用的表格排版
    st.dataframe(filtered, use_container_width=True, hide_index=True)
else:
    st.info("系統準備就緒，請檢查 API 連線以顯示表格。")
