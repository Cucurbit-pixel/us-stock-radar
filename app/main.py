```python
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# 匯入 Alpaca SDK 相關模組
try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestBarRequest
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

# 設定 Streamlit 頁面寬度與標題
st.set_page_config(
    page_title="美股 RS 強度篩選雷達 & Alpaca 實時行情",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 全黑高對比度 CSS 主題 ====================
st.markdown("""
    <style>
        /* 強制將整頁與側邊欄背景設定為純黑 */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
            background-color: #000000 !important;
            color: #F3F4F6 !important;
        }
        
        [data-testid="stSidebar"] {
            background-color: #0C0E14 !important;
            border-right: 1px solid #1F2937;
        }
        
        /* 資訊卡片底色與樣式 */
        .metric-card {
            background-color: #111827 !important;
            padding: 1.2rem;
            border-radius: 12px;
            border: 1px solid #374151 !important;
            border-left: 6px solid #3B82F6 !important;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.5) !important;
            margin-bottom: 1rem;
        }
        
        /* 資金突襲黑馬專屬金卡 */
        .alert-card {
            background-color: #1E1B4B !important;
            padding: 1.2rem;
            border-radius: 12px;
            border: 1px solid #4338CA !important;
            border-left: 6px solid #F59E0B !important;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.6) !important;
            margin-bottom: 1rem;
        }
        
        /* 強制卡片內部字體顏色高對比 */
        .metric-card h4, .alert-card h4 {
            color: #9CA3AF !important;
            margin-top: 0 !important;
            margin-bottom: 0.4rem !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
        }
        .metric-card h3 {
            color: #10B981 !important; /* 螢光綠 */
            margin: 0 !important;
            font-size: 1.9rem !important;
            font-weight: 800 !important;
        }
        .alert-card h3 {
            color: #FBBF24 !important; /* 琥珀金 */
            margin: 0 !important;
            font-size: 1.9rem !important;
            font-weight: 800 !important;
        }
        .metric-card p, .alert-card p {
            color: #D1D5DB !important;
            margin-top: 0.4rem !important;
            margin-bottom: 0 !important;
            font-size: 0.85rem !important;
        }

        .main-title {
            font-size: 2.2rem;
            font-weight: 700;
            color: #3B82F6;
            margin-bottom: 0.3rem;
        }
        .subtitle {
            font-size: 0.95rem;
            color: #9CA3AF;
            margin-bottom: 1.5rem;
        }
        
        .alpaca-status-on {
            background-color: #064E3B;
            color: #34D399;
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: bold;
            display: inline-block;
            border: 1px solid #059669;
        }
        .alpaca-status-off {
            background-color: #78350F;
            color: #FBBF24;
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: bold;
            display: inline-block;
            border: 1px solid #D97706;
        }
    </style>
""", unsafe_allow_html=True)

# ==================== 行業分類中文化對照字典 ====================
INDUSTRY_MAP = {
    "Technology": "科技",
    "Industrials": "工業",
    "Industrial Services": "工業服務",
    "Healthcare": "醫療保健",
    "Health Care": "醫療保健",
    "Consumer Cyclical": "非必需消費品 (週期)",
    "Consumer Discretionary": "非必需消費品",
    "Consumer Defensive": "必需消費品",
    "Consumer Staples": "必需消費品",
    "Financial Services": "金融服務",
    "Financial": "金融",
    "Finance": "金融",
    "Energy": "能源",
    "Basic Materials": "基礎材料",
    "Real Estate": "房地產",
    "Utilities": "公共事業",
    "Communication Services": "通訊服務",
    "Telecommunications": "通訊服務",
    "Other": "其他"
}

# ==================== DATA FETCHING & PROCESSING ====================

@st.cache_data(ttl=43200)  # 快取 12 小時
def load_all_tickers():
    """
    下載全美股基本數據，並自動將行業分類轉換為中文
    """
    url = "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv"
    try:
        df = pd.read_csv(url)
        df['marketCap'] = pd.to_numeric(df['marketCap'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        
        # 排除無效數據
        df = df.dropna(subset=['marketCap', 'volume', 'symbol'])
        
        # 智能轉換行業分類為中文
        df['industry'] = df['industry'].fillna('Other')
        df['industry_zh'] = df['industry'].map(lambda x: INDUSTRY_MAP.get(x, x))
        
        return df
    except Exception as e:
        st.error(f"⚠️ 無法下載美股清單：{e}")
        return pd.DataFrame()

@st.cache_data(ttl=14400)  # 快取 4 小時
def fetch_historical_prices_and_volume(ticker_list):
    """
    安全下載器：一次抓取 1 年歷史收盤價與成交量，完美相容 yfinance 格式
    """
    if not ticker_list:
        return pd.DataFrame(), pd.DataFrame()
        
    yf_tickers = [t.replace('/', '-').replace('.', '-') for t in ticker_list]
    try:
        df = yf.download(yf_tickers, period='1y', interval='1d', progress=False)
        
        if df.empty:
            st.error("⚠️ Yahoo Finance 沒有返回任何歷史數據。")
            return pd.DataFrame(), pd.DataFrame()
            
        df_close = pd.DataFrame()
        df_volume = pd.DataFrame()
        
        # 處理多重層級 MultiIndex DataFrame
        if isinstance(df.columns, pd.MultiIndex):
            if 'Adj Close' in df.columns.levels[0]:
                df_close = df['Adj Close']
            elif 'Close' in df.columns.levels[0]:
                df_close = df['Close']
                
            if 'Volume' in df.columns.levels[0]:
                df_volume = df['Volume']
        # 處理單一索引 DataFrame
        else:
            if 'Adj Close' in df.columns:
                df_close = df[['Adj Close']]
            elif 'Close' in df.columns:
                df_close = df[['Close']]
                
            if 'Volume' in df.columns:
                df_volume = df[['Volume']]
                
        # 確保格式為 DataFrame
        if isinstance(df_close, pd.Series):
            df_close = df_close.to_frame()
        if isinstance(df_volume, pd.Series):
            df_volume = df_volume.to_frame()
            
        return df_close, df_volume
        
    except Exception as e:
        st.error(f"⚠️ 下載股價與成交量歷史數據時出錯：{e}")
        return pd.DataFrame(), pd.DataFrame()

def calculate_rs_scores(df_filtered, df_close):
    """
    計算 William O'Neil / MarketSmith 風格的 RS 相對強度分數
    """
    if df_close.empty:
        return pd.DataFrame()
        
    scores = {}
    perf_1y = {}
    
    for col in df_close.columns:
        series = df_close[col].dropna()
        if len(series) < 180:
            continue
            
        p0 = series.iloc[-1]  # 最新價格
        
        idx_3m = -63 if len(series) >= 63 else 0
        idx_6m = -126 if len(series) >= 126 else 0
        idx_9m = -189 if len(series) >= 189 else 0
        
        p1 = series.iloc[idx_3m]  # 3 個月前
        p2 = series.iloc[idx_6m]  # 6 個月前
        p3 = series.iloc[idx_9m]  # 9 個月前
        p4 = series.iloc[0]       # 1 年前
        
        if p1 == 0 or p2 == 0 or p3 == 0 or p4 == 0:
            continue
            
        weighted_return = (
            ((p0 - p1) / p1 * 40) +
            ((p0 - p2) / p2 * 20) +
            ((p0 - p3) / p3 * 20) +
            ((p0 - p4) / p4 * 20)
        )
        
        scores[col] = weighted_return
        perf_1y[col] = ((p0 - p4) / p4) * 100

    if not scores:
        return pd.DataFrame()
        
    df_scores = pd.DataFrame(list(scores.items()), columns=['yf_symbol', 'weighted_score'])
    df_scores['1Y_Return_Pct'] = df_scores['yf_symbol'].map(perf_1y)
    
    original_symbols = df_filtered['symbol'].tolist()
    yf_to_orig = {s.replace('/', '-').replace('.', '-'): s for s in original_symbols}
    df_scores['symbol'] = df_scores['yf_symbol'].map(yf_to_orig)
    
    df_scores = df_scores.dropna(subset=['symbol'])
    
    if df_scores.empty:
        return pd.DataFrame()
    
    df_scores['RS_Score'] = df_scores['weighted_score'].rank(pct=True) * 98 + 1
    df_scores['RS_Score'] = df_scores['RS_Score'].round(0).astype(int)
    
    result_df = pd.merge(
        df_filtered, 
        df_scores[['symbol', 'RS_Score', '1Y_Return_Pct']], 
        on='symbol', 
        how='inner'
    )
    return result_df

# ==================== 臨玖量能與均線突破算法 ====================
def scan_black_horses(df_final, df_close, df_volume, vol_mult, min_daily_change, max_daily_change, max_ma5_dist):
    """
    黑馬突破算法：
    1. 大資金進場 (當日成交量 >= 20日平均之指定倍數)
    2. 近 5 個交易日每日平均升幅介於 [min_daily_change, max_daily_change] 之間
    3. 最新價貼近 5天均線 (偏離度在 [-1.5%, max_ma5_dist] 之間)
    """
    black_horses = []
    
    for _, row in df_final.iterrows():
        symbol = row['symbol']
        yf_symbol = symbol.replace('/', '-').replace('.', '-')
        
        if yf_symbol not in df_close.columns or yf_symbol not in df_volume.columns:
            continue
            
        close_series = df_close[yf_symbol].dropna()
        vol_series = df_volume[yf_symbol].dropna()
        
        if len(close_series) < 25 or len(vol_series) < 25:
            continue
            
        # 最新價格與成交量
        current_price = close_series.iloc[-1]
        current_vol = vol_series.iloc[-1]
        
        # 1. 20日均量比（大資金進場指標）
        ma20_vol = vol_series.rolling(20).mean().iloc[-1]
        vol_ratio = current_vol / ma20_vol if ma20_vol > 0 else 0
        
        # 2. 近 5 日表現 (計算每日收益率並取平均值)
        last_5_closes = close_series.iloc[-6:] # 獲取 6 天以計算 5 個每日收益
        daily_returns_5d = last_5_closes.pct_change().dropna() * 100
        avg_daily_change = daily_returns_5d.mean()
        cumulative_5d = ((last_5_closes.iloc[-1] - last_5_closes.iloc[0]) / last_5_closes.iloc[0]) * 100
        
        # 3. 偏離 5 天線 % (MA5)
        ma5_price = close_series.rolling(5).mean().iloc[-1]
        ma5_dist = ((current_price - ma5_price) / ma5_price) * 100
        
        # 篩選條件
        if (vol_ratio >= vol_mult) and (min_daily_change <= avg_daily_change <= max_daily_change) and (-1.5 <= ma5_dist <= max_ma5_dist):
            black_horses.append({
                "symbol": symbol,
                "industry_zh": row['industry_zh'],
                "RS_Score": row['RS_Score'],
                "price": current_price,
                "marketCap_Billion": row['marketCap'] / 1_000_000_000,
                "avg_daily_change": round(avg_daily_change, 2),
                "cumulative_5d": round(cumulative_5d, 2),
                "ma5_dist": round(ma5_dist, 2),
                "vol_ratio": round(vol_ratio, 2)
            })
            
    return pd.DataFrame(black_horses)

# ==================== ALPACA REAL-TIME DATA ====================

def get_alpaca_client(api_key, secret_key):
    try:
        client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)
        return client
    except Exception as e:
        st.sidebar.error(f"🔑 Alpaca 金鑰驗證失敗: {e}")
        return None

def fetch_realtime_price_alpaca(symbol, alpaca_client):
    if not alpaca_client:
        return None
    try:
        alpaca_symbol = symbol.replace('-', '/').replace('.', '/')
        request_params = StockLatestBarRequest(symbol_or_symbols=alpaca_symbol)
        latest_bar = alpaca_client.get_stock_latest_bar(request_params)
        
        if alpaca_symbol in latest_bar:
            bar_data = latest_bar[alpaca_symbol]
            return {
                "price": bar_data.close,
                "time": bar_data.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "high": bar_data.high,
                "low": bar_data.low,
                "volume": bar_data.volume
            }
    except Exception as e:
        pass
    return None

# ==================== STREAMLIT INTERFACE ====================

st.markdown('<div class="main-title">📈 美股 RS 強度篩選雷達 & Alpaca 實時行情</div>', unsafe_allow_html=True)

# ------------------ Alpaca 金鑰驗證 ------------------
st.sidebar.header("🔑 Alpaca API 連接設定")

secrets_key = st.secrets.get("ALPACA_API_KEY", "")
secrets_secret = st.secrets.get("ALPACA_SECRET_KEY", "")

if secrets_key and secrets_secret:
    st.sidebar.success("✅ 已自 Streamlit 密鑰庫自動載入 Alpaca 金鑰")
    alpaca_api_key = secrets_key
    alpaca_secret_key = secrets_secret
else:
    alpaca_api_key = st.sidebar.text_input("Alpaca API Key", value="", type="password")
    alpaca_secret_key = st.sidebar.text_input("Alpaca Secret Key", value="", type="password")

alpaca_client = None
if alpaca_api_key and alpaca_secret_key:
    alpaca_client = get_alpaca_client(alpaca_api_key, alpaca_secret_key)

if alpaca_client:
    st.markdown('<div class="alpaca-status-on">● Alpaca 實時報價引擎：已連線</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="alpaca-status-off">● Alpaca 實時報價引擎：未連線（將採用 Yahoo 延遲報價）</div>', unsafe_allow_html=True)

st.write("")

# 載入全部美股資料
with st.spinner("🔍 正在加載全美股基本數據..."):
    df_all = load_all_tickers()

if df_all.empty:
    st.error("❌ 無法載入股票名單，請稍後重試。")
else:
    # ------------------ 側邊欄控制 ------------------
    st.sidebar.header("🛠️ 篩選與排序設定")
    
    # 1. 市值篩選
    min_cap_billion = st.sidebar.slider(
        "最低市值 (億美元)", 
        min_value=5, 
        max_value=500, 
        value=400,  # 預設 400 億
        step=10
    )
    min_cap_value = min_cap_billion * 1_000_000_000
    
    # 2. 交易量篩選
    min_volume = st.sidebar.number_input(
        "最低每日成交量 (股)", 
        min_value=0, 
        value=100000, 
        step=50000
    )
    
    # 3. 中文化行業分類篩選
    all_industries_zh = sorted(df_all['industry_zh'].dropna().unique().tolist())
    selected_industries_zh = st.sidebar.multiselect(
        "選擇行業分類 (可多選，不選代表全選)", 
        options=all_industries_zh,
        default=[]
    )
    
    # 4. 個股搜尋
    search_query = st.sidebar.text_input("🔍 搜尋特定股票代號 (例如: NVDA, AAPL)", "").strip().upper()
    
    # ------------------ 臨玖選股參數自定義區 ------------------
    st.sidebar.markdown("---")
    st.sidebar.header("🚨 爆升黑馬核心指標設定")
    
    vol_mult = st.sidebar.slider(
        "主力大資金進場成交量放大倍數", 
        min_value=1.0, 
        max_value=3.0, 
        value=1.5, 
        step=0.1,
        help="今日成交量與過去20天均量的比率，1.5代表成交量放大50%"
    )
    
    min_daily_change = st.sidebar.slider(
        "近5日平均每日最小升幅 (%)", 
        min_value=1.0, 
        max_value=5.0, 
        value=3.0, 
        step=0.5,
        help="過去5個交易日之每日平均回報的底線值"
    )
    
    max_daily_change = st.sidebar.slider(
        "近5日平均每日最大升幅 (%)", 
        min_value=3.0, 
        max_value=10.0, 
        value=5.0, 
        step=0.5,
        help="限制其上漲熱度，防止選中已過度透支動能的股票"
    )
    
    max_ma5_dist = st.sidebar.slider(
        "最新股價最大偏離5天線 (%)", 
        min_value=2.0, 
        max_value=8.0, 
        value=5.0, 
        step=0.5,
        help="限制最新價格拋離MA5的幅度，防止高位接盤（建議<=5%）"
    )

    st.sidebar.markdown("---")
    # 排序功能
    sort_by = st.sidebar.selectbox(
        "主表排序指標",
        options=["RS_Score", "marketCap", "price"],
        index=0,
        format_func=lambda x: {
            "RS_Score": "RS 相對強度分數 (1-99)",
            "marketCap": "市值 (Market Cap)",
            "price": "最新股價 (Price)"
        }[x]
    )
    
    sort_order = st.sidebar.radio("主表排序方向", ["遞減 (大到小)", "遞增 (小到大)"], index=0)
    ascending_order = True if sort_order == "遞增 (小到大)" else False

    # ------------------ 數據過濾 ------------------
    df_step1 = df_all[(df_all['marketCap'] >= min_cap_value) & (df_all['volume'] >= min_volume)]
    
    if selected_industries_zh:
        df_step1 = df_step1[df_step1['industry_zh'].isin(selected_industries_zh)]
        
    if search_query:
        df_step1 = df_step1[df_step1['symbol'].str.contains(search_query)]

    # ------------------ 核心數據計算 ------------------
    if df_step1.empty:
        st.warning("⚠️ 根據當前篩選條件，沒有符合的股票。請調整市值或行業設定。")
    else:
        tickers_to_fetch = df_step1['symbol'].tolist()
        
        st.info(f"🔄 正在計算 {len(tickers_to_fetch)} 檔大型美股的 1 年加權 RS 強度與歷史成交量數據...（此步驟有快取，初次載入約需 5-10 秒）")
        
        # 升級下載器：同時抓取收盤價與成交量
        df_prices, df_volume = fetch_historical_prices_and_volume(tickers_to_fetch)
        
        # 計算 RS 分數
        df_final = calculate_rs_scores(df_step1, df_prices)
        
        if df_final.empty:
            st.error("❌ 計算 RS 分數時出錯，無法獲取足夠的歷史股價數據。")
        else:
            # 計算臨玖黑馬篩選
            df_black_horses = scan_black_horses(
                df_final, df_prices, df_volume, 
                vol_mult, min_daily_change, max_daily_change, max_ma5_dist
            )
            
            # 排序與格式化主表
            df_final = df_final.sort_values(by=sort_by, ascending=ascending_order)
            df_display = df_final.copy()
            df_display['marketCap_Billion'] = (df_display['marketCap'] / 1_000_000_000).round(2)
            df_display['price'] = df_display['price'].round(2)
            df_display['volume'] = df_display['volume'].apply(lambda x: f"{x:,}")
            
            # ------------------ 頂部看板 (高對比黑底主題) ------------------
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(
                    f'''
                    <div class="metric-card">
                        <h4>📋 符合篩選總數</h4>
                        <h3>{len(df_final)} 檔</h3>
                        <p>市值 ＞ {min_cap_billion} 億美元</p>
                    </div>
                    ''', 
                    unsafe_allow_html=True
                )
            with col2:
                black_horse_count = len(df_black_horses)
                st.markdown(
                    f'''
                    <div class="alert-card">
                        <h4>🚨 資金突襲黑馬 (MA5貼線)</h4>
                        <h3>{black_horse_count} 檔</h3>
                        <p>爆量 + 近5日大升 + 未脫離5天線</p>
                    </div>
                    ''', 
                    unsafe_allow_html=True
                )
            with col3:
                top_stock = df_final.sort_values(by="RS_Score", ascending=False).iloc[0] if not df_final.empty else None
                top_name = f"{top_stock['symbol']} ({top_stock['RS_Score']}分)" if top_stock is not None else "N/A"
                st.markdown(
                    f'''
                    <div class="metric-card">
                        <h4>👑 市場領頭強勢股 (RS 榜首)</h4>
                        <h3>{top_name}</h3>
                        <p>大市強勢先鋒指標</p>
                    </div>
                    ''', 
                    unsafe_allow_html=True
                )

            st.write("")
            
            # ------------------ 主頁頁籤系統 ------------------
            tab_main, tab_black_horse, tab_chart = st.tabs([
                "📊 全市場 RS 篩選雷達", 
                "🚨 臨玖資金突襲黑馬選股器", 
                "🎨 板塊與行業分析"
            ])
            
            # --- Tab 1: 全市場 RS 篩選主表 ---
            with tab_main:
                st.subheader("美股大型板塊 RS 成交清單")
                
                # 重新調整過的格式與前移中文行業分類
                df_table = df_display[[
                    'symbol', 'industry_zh', 'RS_Score', 'price', 'marketCap_Billion'
                ]].rename(columns={
                    'symbol': '股票代碼',
                    'industry_zh': '行業分類',
                    'RS_Score': 'RS 強度得分 (1-99)',
                    'price': '股價 (USD)',
                    'marketCap_Billion': '市值 (億美元)'
                })
                
                st.dataframe(df_table, use_container_width=True, hide_index=True)
                
                # 下載 CSV 
                csv_data = df_table.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 下載篩選數據 (CSV)",
                    data=csv_data,
                    file_name=f"US_Stock_RS_Radar_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="dl_main"
                )
                
            # --- Tab 2: 臨玖資金突襲黑馬選股器 ---
            with tab_black_horse:
                st.subheader("🔥 臨玖資金暴風・爆升黑馬警報板")
                st.write(f"篩選標準：**當日成交量超20日平均量 {vol_mult} 倍** ＋ **近5日均增 {min_daily_change}% - {max_daily_change}%** ＋ **最新價與5日均線相差 <= {max_ma5_dist}%**")
                
                if df_black_horses.empty:
                    st.warning("⚠️ 暫時沒有符合此高標準爆量貼線條件的股票。你可以調整左側的篩選參數試試看！")
                else:
                    df_bh_table = df_black_horses[[
                        'symbol', 'industry_zh', 'RS_Score', 'avg_daily_change', 'cumulative_5d', 'ma5_dist', 'vol_ratio', 'price', 'marketCap_Billion'
                    ]].rename(columns={
                        'symbol': '股票代碼',
                        'industry_zh': '行業分類',
                        'RS_Score': 'RS 得分',
                        'avg_daily_change': '5日均幅 (%)',
                        'cumulative_5d': '5日累計 (%)',
                        'ma5_dist': '偏離5天線 (%)',
                        'vol_ratio': '量比 (20均量)',
                        'price': '股價 (USD)',
                        'marketCap_Billion': '市值 (億美元)'
                    })
                    
                    # 按照量比排序，將資金流入最大的排在最前
                    df_bh_table = df_bh_table.sort_values(by="量比 (20均量)", ascending=False)
                    
                    st.dataframe(df_bh_table, use_container_width=True, hide_index=True)
                    
                    # 導出黑馬名單
                    csv_bh = df_bh_table.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 導出臨玖黑馬名單 (CSV)",
                        data=csv_bh,
                        file_name=f"Black_Horse_Alert_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        key="dl_bh"
                    )
            
            # --- Tab 3: 板塊與行業分析 ---
            with tab_chart:
                st.subheader("🎨 行業與強勢股分佈圖表")
                col_bar, col_pie = st.columns(2)
                
                with col_bar:
                    top_15 = df_final.sort_values(by="RS_Score", ascending=False).head(15)
                    fig_bar = px.bar(
                        top_15,
                        x="symbol",
                        y="RS_Score",
                        color="RS_Score",
                        title="全市場 RS 相對強度排名前 15 名領跑者",
                        labels={"symbol": "股票代碼", "RS_Score": "RS 分數"},
                        color_continuous_scale=px.colors.sequential.Blues,
                        hover_data=["price", "industry_zh"]
                    )
                    fig_bar.update_layout(
                        xaxis_tickangle=-45,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font_color='#F3F4F6'
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                    
                with col_pie:
                    high_rs_stocks = df_final[df_final['RS_Score'] >= 80]
                    if high_rs_stocks.empty:
                        st.write("暫無 RS 分數大於等於 80 的強勢股。")
                    else:
                        industry_counts = high_rs_stocks['industry_zh'].value_counts().reset_index()
                        industry_counts.columns = ['行業分類', '強勢股數量']
                        
                        fig_pie = px.pie(
                            industry_counts,
                            values='強勢股數量',
                            names='行業分類',
                            title="高強度股票 (RS 80+) 的行業與版塊分佈",
                            color_discrete_sequence=px.colors.qualitative.Safe
                        )
                        fig_pie.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)',
                            font_color='#F3F4F6'
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)

            # ------------------ 個股深度歷史趨勢 & Alpaca 實時/盤前數據整合 ------------------
            st.markdown("---")
            st.subheader("🔍 個股 1 年趨勢與 Alpaca 盤前/實時行情")
            
            # 優先加載黑馬清單供快速點擊
            default_options = df_final['symbol'].tolist()
            if not df_black_horses.empty:
                st.info(f"💡 發現 {len(df_black_horses)} 隻爆升黑馬！已在下方名單中置頂優先顯示。")
                default_options = df_black_horses['symbol'].tolist() + [s for s in default_options if s not in df_black_horses['symbol'].tolist()]
                
            selected_ticker = st.selectbox("選擇一檔個股查看實時數據與技術走勢：", options=default_options)
            
            if selected_ticker:
                st.markdown(f"### 🏷️ 股票資訊：{selected_ticker}")
                
                realtime_data = None
                if alpaca_client:
                    with st.spinner("⚡ 正在透過 Alpaca 連接實時報價..."):
                        realtime_data = fetch_realtime_price_alpaca(selected_ticker, alpaca_client)
                
                # Alpaca 實時數據顯示區
                if realtime_data:
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.metric(
                            label="⚡ Alpaca 即時價格 (USD)", 
                            value=f"${realtime_data['price']:.2f}",
                            help="來自 Alpaca 即時數據流（支援盤前與盤後最新一口價）"
                        )
                    with c2:
                        st.metric(label="今日高點 (High)", value=f"${realtime_data['high']:.2f}")
                    with c3:
                        st.metric(label="今日低點 (Low)", value=f"${realtime_data['low']:.2f}")
                    with c4:
                        st.metric(label="最新交易量 (Volume)", value=f"{realtime_data['volume']:,}")
                    st.caption(f"🕒 實時報價時間：{realtime_data['time']}")
                else:
                    matched_stock = df_final[df_final['symbol'] == selected_ticker].iloc[0]
                    st.metric(
                        label="💵 股價 (USD - 延遲)", 
                        value=f"${matched_stock['price']:.2f}",
                        help="Alpaca 未連接，此為 Yahoo Finance 日線關盤價"
                    )
                    if not alpaca_client:
                        st.info("💡 提示：若要啟用盤前零延遲實時報價，請在左側輸入你的 Alpaca API 金鑰！")
                
                # 歷史趨勢圖 (加上 5天線 MA5，以便直觀觀察是否偏離)
                yf_formatted = selected_ticker.replace('/', '-').replace('.', '-')
                if yf_formatted in df_prices.columns:
                    stock_series = df_prices[yf_formatted].dropna()
                    
                    # 計算 MA5
                    ma5_series = stock_series.rolling(5).mean()
                    
                    fig_line = go.Figure()
                    # 1. 股價日線
                    fig_line.add_trace(go.Scatter(
                        x=stock_series.index, y=stock_series.values,
                        mode='lines', name='收盤價 (Close)',
                        line=dict(color='#2563EB', width=2)
                    ))
                    # 2. 5天移動平均線 (MA5)
                    fig_line.add_trace(go.Scatter(
                        x=ma5_series.index, y=ma5_series.values,
                        mode='lines', name='5天線 (MA5)',
                        line=dict(color='#F59E0B', width=1.5, dash='dash')
                    ))
                    
                    fig_line.update_layout(
                        title=f"{selected_ticker} - 近 1 年日 K 線與 5 天均線走勢對照",
                        xaxis_title="日期",
                        yaxis_title="股價 (USD)",
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font_color='#F3F4F6',
                        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                    )
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    st.warning("無該股之詳細歷史價格。")
                    
# 說明欄
st.markdown("""
<div style="background-color: #111827; padding: 1.5rem; border-radius: 10px; margin-top: 2rem; border: 1px solid #1F2937;">
    <h4 style="color: #3B82F6;">💡 什麼是 臨玖·資金暴風黑馬策略？</h4>
    <p style="color: #D1D5DB;">本策略致力於尋找美股大市值標的中，有機構「大資金流入」、近5日展現「強勢拉升慣性」，同時「價格尚未過度拋離」短期支撐線（5天均線）的黑馬爆發點：</p>
    <ul style="color: #D1D5DB;">
        <li><b>量比 (20均量)</b>：篩選今日成交量放大至 20天平均成交量 1.5 倍以上之個股。量先價行，量比放大通常代表大資金主動進場吸籌。</li>
        <li><b>5日均幅 (3% - 5%)</b>：確保股票具有強大上升慣性與動力，但不過度透支，防止買到橫盤不漲的弱勢股。</li>
        <li><b>偏離5天線 (<= 5%)</b>：嚴控風險！只在回調至貼近 5天均線附近（偏離度在 5% 以內）或踩線突破時買入，防止高位接盤。</li>
    </ul>
</div>
""", unsafe_allow_html=True)

```
