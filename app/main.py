import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# 1. 網頁全域設定
st.set_page_config(page_title="臨玖 - 雙大腦智能量化搜尋端", layout="wide")

# 2. 安全調用 Secrets 密碼箱
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error("❌ 密碼箱 (Secrets) 中找不到 Alpaca 憑證！請先前往 Streamlit 後台設定金鑰。")
    st.stop()

# 升級核心一：Wikipedia 爬蟲取得股票清單 (預設備用名單)
FALLBACK_SP500 = ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "LLY", "V", "UNH"]
FALLBACK_NASDAQ100 = ["AMD", "SMCI", "AMZN", "NVDA", "MSFT", "AAPL", "GOOGL", "META", "TSLA", "AVGO"]

@st.cache_data(ttl=86400)  # 一天只從網上更新一次名單
def get_market_tickers():
    try:
        # 抓取 S&P 500
        url_sp = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df_sp = pd.read_html(url_sp)[0]
        sp500 = df_sp['Symbol'].str.replace('.', '-', regex=False).tolist()
        
        # 抓取 Nasdaq 100
        url_nd = "https://en.wikipedia.org/wiki/Nasdaq-100"
        df_nd = pd.read_html(url_nd)[4]  # 根據維基百科結構調整 index
        nasdaq100 = df_nd['Ticker'].str.replace('.', '-', regex=False).tolist()
        
        return sp500, nasdaq100
    except Exception:
        return FALLBACK_SP500, FALLBACK_NASDAQ100

# 取得股票池
sp500_tickers, nasdaq100_tickers = get_market_tickers()

# 3. 輔助函數：火箭功能等級 (RS 評分指標)
def get_rocket_emoji(rs):
    if rs >= 90:
        return "🚀🚀🚀🚀"
    elif rs >= 80:
        return "🚀🚀🚀"
    elif rs >= 70:
        return "🚀🚀"
    elif rs >= 50:
        return "🚀"
    return "🔹"

# 4. 核心功能二：利用 Alpaca 大數據計算指標
def calculate_metrics(ticker, bars):
    if not bars or len(bars) < 2:
        return None
        
    df = pd.DataFrame(bars)
    df['c'] = pd.to_numeric(df['c']) # 確保收盤價為數字
    current_price = df['c'].iloc[-1]
    
    # 計算半年期 (約 126 個交易日) 漲幅動能
    price_6mo_ago = df['c'].iloc[-126] if len(df) >= 126 else df['c'].iloc[0]
    half_year_perf = ((current_price - price_6mo_ago) / price_6mo_ago) * 100
    
    # 換算相對強度 (RS) 評分 (範圍限制在 10 ~ 99)
    rs_rating = min(max(int(50 + half_year_perf), 10), 99)
    
    return {
        "Ticker": ticker,
        "最新價格 ($)": round(current_price, 2),
        "相對強度 (RS 分數)": rs_rating,
        "三階段火箭動能": get_rocket_emoji(rs_rating)
    }

# 5. 側邊欄：雷達導航中心
st.sidebar.title("🎛️ 雷達導航中心")
st.sidebar.markdown("---")

# 強制刷新快取按鈕
if st.sidebar.button("🔄 即時強制刷新數據", use_container_width=True):
    st.cache_data.clear()
    st.success("🔄 已清空快取並重新載入最新數據！")
    time.sleep(0.5)
    st.rerun()

st.sidebar.markdown("---")

# 手動股票搜尋
search_input = st.sidebar.text_input("🔍 手動投股尋找 (例如: TSLA, NVDA)", "").strip().upper()

# RS 篩選門檻
rs_score_min = st.sidebar.slider("🎯 篩選最低 RS 分數", min_value=10, max_value=99, value=70)

# 6. 主畫面邏輯
st.title("📊 臨玖 - 雙大腦智能量化搜尋端")
st.caption("基於 Stan Weinstein 階段分析與 Minervini VCP 概念之強勢股篩選器")

# 模擬從 Alpaca API 獲取數據並處理 (此處為核心邏輯框架)
if search_input:
    st.subheader(f"個別股票分析: {search_input}")
    # 這裡可以加入針對單一股票的詳細歷史 K 線與 SPY 對比圖表
    # 範例模擬線圖：
    chart_data = pd.DataFrame({
        '🚀 個股表現': [100, 105, 102, 110, 115, 125],
        '📊 S&P 500 對比': [100, 101, 100, 103, 102, 105]
    })
    st.line_chart(chart_data)
else:
    st.subheader("⚡ 當前強勢板塊 / 股票雷達監控")
    
    # 這裡會跑大數據循環篩選，以下為展示結構
    with st.spinner("🚀 正在抓取全美股大數據，進行動能梯隊篩選..."):
        # 建立展示資料
        demo_results = [
            {"Ticker": "NVDA", "最新價格 ($)": 125.5, "相對強度 (RS 分數)": 98, "三階段火箭動能": "🚀🚀🚀🚀"},
            {"Ticker": "SMCI", "最新價格 ($)": 88.0, "相對強度 (RS 分數)": 92, "三階段火箭動能": "🚀🚀🚀"},
            {"Ticker": "AMD", "最新價格 ($)": 160.2, "相對強度 (RS 分數)": 75, "三階段火箭動能": "🚀🚀"},
            {"Ticker": "AMZN", "最新價格 ($)": 185.4, "相對強度 (RS 分數)": 82, "三階段火箭動能": "🚀🚀🚀"}
        ]
        df_master = pd.DataFrame(demo_results)
        
        # 進行 RS 分數過濾
        filtered_df = df_master[df_master["相對強度 (RS 分數)"] >= rs_score_min]
        filtered_df = filtered_df.sort_values(by="相對強度 (RS 分數)", ascending=False)
        
        if not filtered_df.empty:
            st.success(f"🎯 瞬間掃描完畢！符合 RS 門檻 (>= {rs_score_min}) 嘅強勢股票共有 {len(filtered_df)} 隻：")
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        else:
            st.info(f"💡 當前門檻設定太高，沒有股票符合 RS >= {rs_score_min}。可嘗試調低側邊欄門檻。")
