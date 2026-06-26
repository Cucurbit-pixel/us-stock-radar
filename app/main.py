import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. 網頁全域設定
st.set_page_config(page_title="臨玖 - GICS 極速量化強勢股雷達", layout="wide")

# 2. 安全調用 Secrets 密碼箱
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error("❌ 密碼箱 (Secrets) 中找不到 Alpaca 憑證！請先前往 Streamlit Settings 設定好金鑰。")
    st.stop()

# 3. 嚴格對齊 GICS 11 大行業分類映射表
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

# 🌟 核心優化：將「API獲取」同「所有數學計算」一併打包快取，每小時只算一次
@st.cache_data(ttl=3600)
def load_and_calculate_master_data():
    tickers = list(SECTOR_MAP.keys())
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
            return pd.DataFrame()
        all_bars = response.json().get("bars", {})
    except Exception:
        return pd.DataFrame()
        
    results = []
    for ticker, bars in all_bars.items():
        if len(bars) < 150: 
            continue
            
        df = pd.DataFrame(bars)
        df['close'] = df['c']
        
        current_price = df['close'].iloc[-1]
        
        # 計算半年期 (126個交易日) 漲跌幅動能
        price_6mo_ago = df['close'].iloc[-126] if len(df) >= 126 else df['close'].iloc[0]
        half_year_perf = ((current_price - price_6mo_ago) / price_6mo_ago) * 100
        
        # 換算相對強度 (RS) 評分
        rs_rating = min(max(int(50 + half_year_perf), 10), 99)
        sector_name = SECTOR_MAP.get(ticker, "其他")
        
        results.append({
            "股票代號": ticker,
            "GICS 行業": sector_name,
            "最新現價 ($)": round(current_price, 2),
            "相對強度 (RS 分數)": rs_rating,
            "三級火箭動能": get_rocket_emoji(rs_rating)
        })
        
    return pd.DataFrame(results)

# 4. 【左側側邊欄】雷達導航中心 (設定篩選條件)
st.sidebar.title("🤖 雷達導航中心")
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ GICS 量化濾網")

gics_sectors = [
    "全部", "資訊科技", "醫療保健", "非必需消費品", "金融", "通訊服務",
    "工業", "必需消費品", "能源", "原物料", "公用事業", "房地產"
]
# 當這裡的數值改變時，Streamlit 會全速刷新
selected_sector = st.sidebar.selectbox("選擇行業分類 (GICS)", gics_sectors)
rs_score_min = st.sidebar.slider("最低相對強度 (RS) 分數", 10, 99, 70)

st.sidebar.markdown("---")
st.sidebar.caption("數據源：Alpaca API 數據全自動對接")

# 5. 【右側主畫面】瞬間渲染
st.title("📈 臨玖量化雷達中心")
st.markdown(f"### 當前聚焦板塊：`{selected_sector}`")

# 獲取已計算完畢的大總表（直接從內存提取，速度極快）
with st.spinner("🤖 正在從大數據庫提取即時雷達數據..."):
    master_df = load_and_calculate_master_data()

if not master_df.empty:
    # ⚡ 0毫秒極速過濾邏輯
    filtered_df = master_df.copy()
    
    # 條件一：行業篩選
    if selected_sector != "全部":
        filtered_df = filtered_df[filtered_df["GICS 行業"] == selected_sector]
        
    # 條件二：RS 分數篩選
    filtered_df = filtered_df[filtered_df["相對強度 (RS 分數)"] >= rs_score_min]
    
    # 排序並輸出
    if not filtered_df.empty:
        filtered_df = filtered_df.sort_values(by="相對強度 (RS 分數)", ascending=False)
        st.success(f"🎉 瞬間篩選成功！符合條件的強勢標的共有 {len(filtered_df)} 隻：")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    else:
        st.info("⚠️ 💡 當前篩選條件下，暫時沒有符合最低 RS 分數的強勢股。")
else:
    st.warning("⚠️ 大數據加載失敗，請檢查 Alpaca 金鑰狀態或網絡連線。")
