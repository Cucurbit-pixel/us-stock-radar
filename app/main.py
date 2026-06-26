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

# RS 評分
rs_score = st.sidebar.slider("最低相對強度 (RS) 分數", min_value=10, max_value=99, value=70)
st.sidebar.caption("數據來源：Alpaca API 大數據全自動對接")

# 4. 【石英工業】指標 & 大數據基準
st.markdown("### 📊 大數據量化網頁")

# 5. 全自動數據 (API) 呼叫函數
@st.cache_data
def fetch_market_data(tickers):
    data_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
    }
    
    # 前推約 256 天的 K 線，用以計算 150 日線 (30 週線)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    params = {
        "symbols": ",".join(tickers),
        "timeframe": "1Day",
        "start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "adjustment": "all",
        "feed": "iex"  # <--- 修正核心：強制指定使用 IEX 免費數據源，避開 SIP 權限報錯
    }
    
    response = requests.get(data_url, headers=headers, params=params)
    
    if response.status_code == 401:
        st.error(f"❌ Alpaca 錯誤 (401 Unauthorized) | 請確認 Secrets 中的金鑰對是否正確，或是小心複製到了空格。")
        return None
    elif response.status_code != 200:
        st.error(f"❌ 數據提取失敗。狀態碼: {response.status_code}，錯誤訊息: {response.text}")
        return None
        
    return response.json().get("bars", {})

# 6. 執行大數據掃描與量化計算
with st.spinner("🤖 正在穿透 Alpaca 交易所，實時計算強勢股數據..."):
    # 這裡的 WATCH_LIST 是假設你之前定義過，如果未定義請確保你有傳入列表
    # 如果你是從另外一個檔案匯入，請確保這裡能存取到
    WATCH_LIST = ["NVDA", "AMD", "SMCI", "AMZN", "AAPL", "MSFT", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX"]
    all_bars = fetch_market_data(WATCH_LIST)

if all_bars:
    processed_results = []
    
    for ticker, bars in all_bars.items():
        if len(bars) < 200:  # 確保有足夠歷史數據計算 150日線
            continue
            
        df = pd.DataFrame(bars)
        df['close'] = df['c'] # 統一欄位名稱
        
        # 計算 150 日線 (約 30 週)
        df['ma150'] = df['close'].rolling(window=150).mean()
        
        # 當前價格
        current_price = df['close'].iloc[-1]
        ma150 = df['ma150'].iloc[-1]
        
        # 計算 RS 評分 (簡單版範例)
        rs_rating = min(int(50 + half_year_perf), 100) # 假設有計算邏輯
        
        # 篩選階段
        if market_stage_filter != "全部":
             # 這裡加入你的階段判斷邏輯
             pass
             
        processed_results.append({
            "ticker": ticker,
            "price": current_price,
            "ma150": ma150,
            "rs": rs_rating
        })

    # 7. 渲染表格
    report_df = pd.DataFrame(processed_results)
    if not report_df.empty:
        st.success("✅ 數據擷取成功！")
        st.dataframe(report_df)
    else:
        st.warning("⚠️ 沒有符合篩選條件的股票。")
else:
    st.info("請檢查網絡或 API 設定。")
