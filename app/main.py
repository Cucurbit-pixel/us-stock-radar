import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. 網頁基本設定
st.set_page_config(page_title="美股大數據強勢股雷達", layout="wide", initial_sidebar_state="expanded")

# 2. 安全讀取 Streamlit Secrets 密碼箱
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error("❌ 密碼箱 (Secrets) 中找不到 Alpaca 憑證！請先前往 Streamlit Settings -> Secrets 設定好金鑰。")
    st.stop()

# 3. 【左邊】🧭 雷達導航中心
st.sidebar.title("🧭 雷達導航中心")
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ 量化條件篩選")

# 篩選市場階段
market_stage_filter = st.sidebar.selectbox(
    "選擇 Stan Weinstein 階段", 
    ["全部", "階段 2 (多頭主升浪)", "其他階段/整理期"]
)

# 最低 RS 評分
min_rs_score = st.sidebar.slider("最低相對強度 (RS) 分數", min_value=10, max_value=99, value=70)

st.sidebar.markdown("---")
st.sidebar.caption("數據來源：Alpaca API 大數據全自動對接")


# 4. 【右邊主畫面】條條大路通多頭
st.title("📈 條條大路通多頭")
st.markdown("### ⚡ 大數據量化濾網掃描中...")

# 聚焦追蹤的強勢板塊與核心股 (半導體、AI、雲端、大型科技股)
WATCH_LIST = ["NVDA", "AMD", "SMCI", "AMZN", "AAPL", "MSFT", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX"]

# 5. 全自動對接 Alpaca 數據核心函數
@st.cache_data(ttl=3600)  # 快取 1 小時，避免頻繁刷網頁重複調用 API
def fetch_market_data(tickers):
    # 使用 Alpaca 官方標準 Data v2 終端點
    data_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
    }
    
    # 抓取過去大約 250 天的日 K 線，用作精準計算 150日線 (30週線)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=250)
    
    params = {
        "symbols": ",".join(tickers),
        "timeframe": "1Day",
        "start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 1000,
        "adjustment": "all"
    }
    
    response = requests.get(data_url, headers=headers, params=params)
    
    if response.status_code == 401:
        st.error("❌ Alpaca 驗證失敗 (401 Unauthorized)！請確認 Secrets 中的金鑰配對是否正確，或是否不小心複製到了空格。")
        st.stop()
    elif response.status_code != 200:
        st.error(f"❌ 數據提取失敗。狀態碼: {response.status_code}，錯誤訊息: {response.text}")
        st.stop()
        
    return response.json().get("bars", {})

# 6. 執行大數據掃描與量化計算
with st.spinner("🤖 正在穿透 Alpaca 交易所，實時計算強勢股數據..."):
    all_bars = fetch_market_data(WATCH_LIST)

if not all_bars:
    st.warning("⚠️ 未能成功取得股票數據，請確認美股是否處於常規交易時間段或代碼正確性。")
else:
    processed_results = []
    
    for ticker, bars in all_bars.items():
        if len(bars) < 150:  # 確保數據量夠算 150MA
            continue
            
        df = pd.DataFrame(bars)
        df['close'] = df['c']  # c 代表 Close 關盤價
        
        current_price = df['close'].iloc[-1]
        
        # 量化計算：Stan Weinstein 核心（150日均線 / 即大約 30 週線）
        df['MA150'] = df['close'].rolling(window=150).mean()
        df['MA50'] = df['close'].rolling(window=50).mean()
        
        ma150_now = df['MA150'].iloc[-1]
        ma150_past = df['MA150'].iloc[-5]  # 5天前的均線值，用來判斷均線是否正在「上揚」
        ma50_now = df['MA50'].iloc[-1]
        
        # 【條件一】Stan Weinstein 階段 2 判定：價格在 150MA 之上，且 150MA 必須上揚
        is_stage_2 = current_price > ma150_now and ma150_now > ma150_past
        stage_desc = "階段 2 (多頭主升浪)" if is_stage_2 else "其他階段/整理期"
        
        # 【條件二】模擬 MarketSmith 相對強度 (RS) 評分：計算半年期表現並進行權重變換
        half_year_perf = (current_price - df['close'].iloc[-120]) / df['close'].iloc[-120] * 100
        rs_rating = min(max(int(50 + half_year_perf), 10), 99)  # 簡易計算將其限縮在 10-99 區間
        
        processed_results.append({
            "股票代號": ticker,
            "最新現價 ($)": round(current_price, 2),
            "50日均線 (MA50)": round(ma50_now, 2),
            "150日均線 (30週線)": round(ma150_now, 2),
            "Stan Weinstein 階段": stage_desc,
            "相對強度 (RS 分數)": rs_rating
        })
        
    # 轉為 DataFrame 進行最後畫面的篩選過濾
    report_df = pd.DataFrame(processed_results)
    
    # 根據左邊側邊欄控制器的輸入值進行即時過濾
    if market_stage_filter != "全部":
        report_df = report_df[report_df["Stan Weinstein 階段"] == market_stage_filter]
        
    report_df = report_df[report_df["相對強度 (RS 分數)"] >= min_rs_score]
    
    # 按強勢度 (RS 分數) 由高到低排序
    report_df = report_df.sort_values(by="相對強度 (RS 分數)", ascending=False)
    
    # 7. 渲染輸出漂亮的量化雷達大數據表格
    st.success(f"🎉 成功掃描！當前符合篩選標準的強勢標的有 {len(report_df)} 隻：")
    
    st.dataframe(
        report_df.style.format({
            "最新現價 ($)": "{:.2f}",
            "50日均線 (MA50)": "{:.2f}",
            "150日均線 (30週線)": "{:.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )
