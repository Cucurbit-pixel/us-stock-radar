import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. 網頁全域設定
st.set_page_config(page_title="臨玖 - GICS 全自動量化強勢股雷達", layout="wide")

# 2. 安全調用 Secrets 密碼箱
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error("❌ 密碼箱 (Secrets) 中找不到 Alpaca 憑證！請先前往 Streamlit Settings 設定好金鑰。")
    st.stop()

# 3. 嚴格對齊 GICS 11 大行業分類映射表 (已為你擴充各板塊權重龍頭)
SECTOR_MAP = {
    # === 1. 資訊科技 (Information Technology) ===
    "AAPL": "資訊科技", "MSFT": "資訊科技", "NVDA": "資訊科技", "AMD": "資訊科技", 
    "AVGO": "資訊科技", "SMCI": "資訊科技", "MSI": "資訊科技", "INTU": "資訊科技", 
    "TSM": "資訊科技", "ARM": "資訊科技",
    
    # === 2. 醫療保健 (Health Care) ===
    "LLY": "醫療保健", "UNH": "醫療保健", "JNJ": "醫療保健",
    
    # === 3. 非必需消費品 (Consumer Discretionary) ===
    "AMZN": "非必需消費品", "TSLA": "非必需消費品", "HD": "非必需消費品",
    
    # === 4. 金融 (Financials) ===
    "V": "金融", "MA": "金融", "JPM": "金融",
    
    # === 5. 通訊服務 (Communication Services) ===
    "GOOGL": "通訊服務", "META": "通訊服務", "NFLX": "通訊服務",
    
    # === 6. 工業 (Industrials) ===
    "CAT": "工業", "GE": "工業", "HON": "工業",
    
    # === 7. 必需消費品 (Consumer Staples) ===
    "COST": "必需消費品", "PG": "必需消費品", "WMT": "必需消費品",
    
    # === 8. 能源 (Energy) ===
    "XOM": "能源", "CVX": "能源",
    
    # === 9. 原物料 (Materials) ===
    "LIN": "原物料", "FCX": "原物料",
    
    # === 10. 公用事業 (Utilities) ===
    "NEE": "公用事業",
    
    # === 11. 房地產 (Real Estate) ===
    "PLD": "房地產", "AMT": "房地產"
}

# 輔助函數：火箭動能等級
def get_rocket_emoji(rs):
    if rs >= 85: return "🚀🚀🚀"
    if rs >= 70: return "🚀🚀"
    return "🚀"

# 4. 全自動大數據對接函數 (免費帳戶強制指定 feed: iex)
@st.cache_data(ttl=3600)
def fetch_market_data(tickers):
    data_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
    }
    params = {
        "symbols": ",".join(tickers),
        "timeframe": "1Day",
        "start": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "feed": "iex",
        "adjustment": "all"
    }
    try:
        response = requests.get(data_url, headers=headers, params=params)
        if response.status_code != 200:
            return {}
        return response.json().get("bars", {})
    except Exception:
        return {}

# 5. 【左側側邊欄】雷達導航中心
st.sidebar.title("🤖 雷達導航中心")
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ GICS 量化濾網")

# 定義嚴格的 11 大行業下拉選單順序
gics_sectors = [
    "全部",
    "資訊科技", "醫療保健", "非必需消費品", "金融", "通訊服務",
    "工業", "必需消費品", "能源", "原物料", "公用事業", "房地產"
]
selected_sector = st.sidebar.selectbox("選擇行業分類 (GICS)", gics_sectors)

# 最低相對強度分數滑桿
rs_score_min = st.sidebar.slider("最低相對強度 (RS) 分數", 10, 99, 70)
st.sidebar.markdown("---")
st.sidebar.caption("數據源：Alpaca API 數據全自動對接")

# 6. 【右側主畫面】渲染輸出
st.title("📈 臨玖量化雷達中心")
st.markdown(f"### 當前聚焦板塊：`{selected_sector}`")

# 自動從對照表抓取所有的股票代號
WATCH_LIST = list(SECTOR_MAP.keys())

with st.spinner("🤖 正在穿透交易所，實時計算 11 大板塊量化數據..."):
    all_bars = fetch_market_data(WATCH_LIST)

if all_bars:
    processed_results = []
    
    for ticker, bars in all_bars.items():
        if len(bars) < 150: 
            continue
            
        df = pd.DataFrame(bars)
        df['close'] = df['c']  # c 代表 Close 收盤價
        
        current_price = df['close'].iloc[-1]
        
        # 計算半年期 (126個交易日) 漲跌幅動能
        price_6mo_ago = df['close'].iloc[-126] if len(df) >= 126 else df['close'].iloc[0]
        half_year_perf = ((current_price - price_6mo_ago) / price_6mo_ago) * 100
        
        # 換算為 10-99 的相對強度 (RS) 評分
        rs_rating = min(max(int(50 + half_year_perf), 10), 99)
        
        # 獲取該股票的 GICS 行業名稱
        sector_name = SECTOR_MAP.get(ticker, "其他")
        
        # 觸發雙重濾網：1. 行業分類必須吻合 2. RS 分數必須達標
        if (selected_sector == "全部" or sector_name == selected_sector) and (rs_rating >= rs_score_min):
            processed_results.append({
                "股票代號": ticker,
                "GICS 行業": sector_name,
                "最新現價 ($)": round(current_price, 2),
                "相對強度 (RS 分數)": rs_rating,
                "三級火箭動能": get_rocket_emoji(rs_rating)
            })

    # 顯示量化篩選報告表格
    if processed_results:
        report_df = pd.DataFrame(processed_results).sort_values(by="相對強度 (RS 分數)", ascending=False)
        st.success(f"🎉 掃描成功！當前符合條件的強勢標的共有 {len(report_df)} 隻：")
        st.dataframe(report_df, use_container_width=True, hide_index=True)
    else:
        st.info("⚠️ 💡 當前篩選條件或該行業下，暫時沒有符合最低 RS 分數的強勢股。嘗試調低左側的 RS 分數再看看？")
else:
    st.warning("⚠️ 數據獲取失敗，請確認網路連線或金鑰狀態。")
