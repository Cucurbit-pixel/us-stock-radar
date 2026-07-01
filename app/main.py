```python
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

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

# 自定義 CSS 樣式提升 UI 美感
st.markdown("""
    <style>
        .main-title {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1E3A8A;
            margin-bottom: 0.5rem;
        }
        .subtitle {
            font-size: 1.1rem;
            color: #4B5563;
            margin-bottom: 2rem;
        }
        .metric-card {
            background-color: #F3F4F6;
            padding: 1.2rem;
            border-radius: 10px;
            border-left: 5px solid #2563EB;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .alpaca-status-on {
            background-color: #DCFCE7;
            color: #15803D;
            padding: 0.3rem 0.8rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: bold;
            display: inline-block;
        }
        .alpaca-status-off {
            background-color: #FEF3C7;
            color: #92400E;
            padding: 0.3rem 0.8rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: bold;
            display: inline-block;
        }
    </style>
""", unsafe_allow_html=True)

# ==================== DATA FETCHING & PROCESSING ====================

@st.cache_data(ttl=43200)  # 快取 12 小時
def load_all_tickers():
    """
    從自動更新的 GitHub 倉庫下載全美股名單（含市值、成交量、行業與板塊分類）
    """
    url = "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv"
    try:
        df = pd.read_csv(url)
        # 確保重要數值欄位為數值格式
        df['marketCap'] = pd.to_numeric(df['marketCap'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        # 排除沒有成交量或市值缺失的股票
        df = df.dropna(subset=['marketCap', 'volume', 'symbol'])
        return df
    except Exception as e:
        st.error(f"⚠️ 無法下載美股清單：{e}")
        return pd.DataFrame()

@st.cache_data(ttl=14400)  # 快取 4 小時
def fetch_historical_prices(ticker_list):
    """
    極致安全版：批次下載並智能解析收盤價，兼容各種 yfinance 回傳格式
    """
    if not ticker_list:
        return pd.DataFrame()
        
    yf_tickers = [t.replace('/', '-').replace('.', '-') for t in ticker_list]
    try:
        # 下載數據
        df = yf.download(yf_tickers, period='1y', interval='1d', progress=False)
        
        if df.empty:
            st.error("⚠️ Yahoo Finance 沒有返回任何歷史股價數據。")
            return pd.DataFrame()
            
        df_close = pd.DataFrame()
        
        # 1. 處理標準多重索引 DataFrame (下載多隻股票成功時)
        if isinstance(df.columns, pd.MultiIndex):
            if 'Adj Close' in df.columns.levels[0]:
                df_close = df['Adj Close']
            elif 'Close' in df.columns.levels[0]:
                df_close = df['Close']
                
        # 2. 處理單一索引 DataFrame (單隻股票或欄位被扁平化)
        else:
            if 'Adj Close' in df.columns:
                df_close = df[['Adj Close']]
            elif 'Close' in df.columns:
                df_close = df[['Close']]
            else:
                # 處理可能的扁平化欄位 (例如: 'Adj Close_AAPL' 或 'AAPL_Adj Close')
                adj_cols = [c for c in df.columns if 'Adj Close' in str(c)]
                if adj_cols:
                    df_close = df[adj_cols]
                    # 嘗試簡化欄位名稱為股票代碼
                    df_close.columns = [str(c).replace('Adj Close_', '').replace('_Adj Close', '') for c in df_close.columns]
                else:
                    close_cols = [c for c in df.columns if 'Close' in str(c)]
                    if close_cols:
                        df_close = df[close_cols]
                        df_close.columns = [str(c).replace('Close_', '').replace('_Close', '') for c in df_close.columns]
                        
        if df_close.empty:
            st.error("⚠️ 無法從 Yahoo Finance 返回的資料中定位收盤價欄位。")
            return pd.DataFrame()
            
        # 確保回傳的是 DataFrame 格式
        if isinstance(df_close, pd.Series):
            df_close = df_close.to_frame()
            
        return df_close
        
    except Exception as e:
        st.error(f"⚠️ 下載股價歷史數據時出錯：{e}")
        return pd.DataFrame()

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
            
        # IBD 加權相對強度公式 (近 3 個月佔 40%)
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
    
    # 過濾掉無法對應原始 symbol 的列
    df_scores = df_scores.dropna(subset=['symbol'])
    
    if df_scores.empty:
        return pd.DataFrame()
    
    # 計算 1 到 99 的百分位排名 (Percentile Rank)
    df_scores['RS_Score'] = df_scores['weighted_score'].rank(pct=True) * 98 + 1
    df_scores['RS_Score'] = df_scores['RS_Score'].round(0).astype(int)
    
    result_df = pd.merge(
        df_filtered, 
        df_scores[['symbol', 'RS_Score', '1Y_Return_Pct']], 
        on='symbol', 
        how='inner'
    )
    return result_df

# ==================== ALPACA REAL-TIME DATA ====================

def get_alpaca_client(api_key, secret_key):
    """
    初始化 Alpaca 歷史與實時數據客戶端
    """
    if not ALPACA_AVAILABLE:
        return None
    try:
        client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)
        return client
    except Exception as e:
        st.sidebar.error(f"🔑 Alpaca 金鑰驗證失敗: {e}")
        return None

def fetch_realtime_price_alpaca(symbol, alpaca_client):
    """
    使用 Alpaca 獲取最即時的最後一根 K 線收盤價
    """
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

st.markdown('<div class="main-title">📈 美股 RS 相對強度雷達 & Alpaca 實時行情</div>', unsafe_allow_html=True)

# ------------------ Alpaca 金鑰驗證與設定 ------------------
st.sidebar.header("🔑 Alpaca API 連接設定")

# 優先檢查 Streamlit Secrets
secrets_key = st.secrets.get("ALPACA_API_KEY", "")
secrets_secret = st.secrets.get("ALPACA_SECRET_KEY", "")

if secrets_key and secrets_secret:
    st.sidebar.success("✅ 已自 Streamlit 密鑰庫自動載入 Alpaca 金鑰")
    alpaca_api_key = secrets_key
    alpaca_secret_key = secrets_secret
else:
    alpaca_api_key = st.sidebar.text_input("Alpaca API Key", value="", type="password")
    alpaca_secret_key = st.sidebar.text_input("Alpaca Secret Key", value="", type="password")

# 初始化 Alpaca 客戶端
alpaca_client = None
if alpaca_api_key and alpaca_secret_key:
    alpaca_client = get_alpaca_client(alpaca_api_key, alpaca_secret_key)

# 顯示 Alpaca 即時狀態
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
        step=10,
        help="MarketSmith 通常專注於具有法人機構青睞的中大型強勢股。"
    )
    min_cap_value = min_cap_billion * 1_000_000_000
    
    # 2. 交易量篩選
    min_volume = st.sidebar.number_input(
        "最低每日成交量 (股)", 
        min_value=0, 
        value=100000, 
        step=50000
    )
    
    # 3. 行業分類篩選
    all_industries = sorted(df_all['industry'].dropna().unique().tolist())
    selected_industries = st.sidebar.multiselect(
        "選擇行業分類 (可多選，不選代表全選)", 
        options=all_industries,
        default=[]
    )
    
    # 4. 個股搜尋
    search_query = st.sidebar.text_input("🔍 搜尋特定股票代號 (例如: NVDA, AAPL)", "").strip().upper()
    
    # 5. 排序功能
    sort_by = st.sidebar.selectbox(
        "排序指標",
        options=["RS_Score", "marketCap", "price", "1Y_Return_Pct"],
        index=0,
        format_func=lambda x: {
            "RS_Score": "RS 相對強度分數 (1-99)",
            "marketCap": "市值 (Market Cap)",
            "price": "最新股價 (Price)",
            "1Y_Return_Pct": "1年累積漲幅 (%)"
        }[x]
    )
    
    sort_order = st.sidebar.radio("排序方向", ["遞減 (大到小)", "遞增 (小到大)"], index=0)
    ascending_order = True if sort_order == "遞增 (小到大)" else False

    # ------------------ 數據過濾 ------------------
    df_step1 = df_all[(df_all['marketCap'] >= min_cap_value) & (df_all['volume'] >= min_volume)]
    
    if selected_industries:
        df_step1 = df_step1[df_step1['industry'].isin(selected_industries)]
        
    if search_query:
        df_step1 = df_step1[df_step1['symbol'].str.contains(search_query)]

    # ------------------ RS 分數核心計算 ------------------
    if df_step1.empty:
        st.warning("⚠️ 根據當前篩選條件，沒有符合的股票。請調整市值或行業設定。")
    else:
        tickers_to_fetch = df_step1['symbol'].tolist()
        
        st.info(f"🔄 正在計算 {len(tickers_to_fetch)} 檔大型美股的 1 年加權 RS 強度分數...（此步驟有快取，初次載入約需 5-10 秒）")
        
        # 抓取歷史價格 (呼叫升級版函數)
        df_prices = fetch_historical_prices(tickers_to_fetch)
        
        # 計算 RS 分數與排名
        df_final = calculate_rs_scores(df_step1, df_prices)
        
        if df_final.empty:
            st.error("❌ 計算 RS 分數時出錯，無法獲取足夠的歷史股價數據。")
        else:
            # 套用用戶選定的排序方式
            df_final = df_final.sort_values(by=sort_by, ascending=ascending_order)
            
            # 格式化欄位以便精美展示
            df_display = df_final.copy()
            df_display['marketCap_Billion'] = (df_display['marketCap'] / 1_000_000_000).round(2)
            df_display['1Y_Return_Pct'] = df_display['1Y_Return_Pct'].round(2)
            df_display['price'] = df_display['price'].round(2)
            df_display['volume'] = df_display['volume'].apply(lambda x: f"{x:,}")
            
            # ------------------ 關鍵指標看板 ------------------
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(
                    f'<div class="metric-card"><h4>📋 符合篩選總數</h4><h3>{len(df_final)} 檔</h3><p>市值 ＞ {min_cap_billion} 億美元</p></div>', 
                    unsafe_allow_html=True
                )
            with col2:
                top_stock = df_final.sort_values(by="RS_Score", ascending=False).iloc[0] if not df_final.empty else None
                top_name = f"{top_stock['symbol']} ({top_stock['RS_Score']}分)" if top_stock is not None else "N/A"
                st.markdown(
                    f'<div class="metric-card"><h4>👑 當前市場最強 (RS 榜首)</h4><h3>{top_name}</h3><p>{top_stock["name"] if top_stock is not None else ""}</p></div>', 
                    unsafe_allow_html=True
                )
            with col3:
                avg_return = df_final['1Y_Return_Pct'].mean()
                st.markdown(
                    f'<div class="metric-card"><h4>📈 篩選名單平均年回報</h4><h3>{avg_return:.2f}%</h3><p>對比 S&P 500 平均表現</p></div>', 
                    unsafe_allow_html=True
                )

            st.write("")
            
            # ------------------ 數據主表展示 ------------------
            st.subheader("📊 篩選結果數據表")
            
            df_table = df_display[[
                'symbol', 'name', 'RS_Score', '1Y_Return_Pct', 'price', 'marketCap_Billion', 'industry'
            ]].rename(columns={
                'symbol': '股票代碼',
                'name': '公司名稱',
                'RS_Score': 'RS 強度得分 (1-99)',
                '1Y_Return_Pct': '1年累積回報 (%)',
                'price': '股價 (USD)',
                'marketCap_Billion': '市值 (億美元)',
                'industry': '行業分類'
            })
            
            st.dataframe(df_table, use_container_width=True, hide_index=True)
            
            # 提供 CSV 下載按鈕
            csv_data = df_table.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 下載篩選數據 (CSV)",
                data=csv_data,
                file_name=f"US_Stock_RS_Radar_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

            st.markdown("---")
            
            # ------------------ 可視化圖表 ------------------
            st.subheader("🎨 強勢板塊與領先股可視化")
            
            tab1, tab2 = st.tabs(["🔥 Top 15 領頭強勢股", "🏢 行業板塊分佈"])
            
            with tab1:
                top_15 = df_final.sort_values(by="RS_Score", ascending=False).head(15)
                fig_bar = px.bar(
                    top_15,
                    x="symbol",
                    y="RS_Score",
                    color="1Y_Return_Pct",
                    title="當前全市場 RS 相對強度分數前 15 名領跑者",
                    labels={"symbol": "股票代碼", "RS_Score": "RS 分數 (越高越強)", "1Y_Return_Pct": "1年累積漲幅 (%)"},
                    color_continuous_scale=px.colors.sequential.Viridis,
                    hover_data=["name", "price", "industry"]
                )
                fig_bar.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with tab2:
                high_rs_stocks = df_final[df_final['RS_Score'] >= 80]
                if high_rs_stocks.empty:
                    st.write("暫無 RS 分數大於等於 80 的強勢股。")
                else:
                    industry_counts = high_rs_stocks['industry'].value_counts().reset_index()
                    industry_counts.columns = ['行業分類', '強勢股數量 (RS>=80)']
                    
                    fig_pie = px.pie(
                        industry_counts,
                        values='強勢股數量 (RS>=80)',
                        names='行業分類',
                        title="高強度股票 (RS Rating 80+) 的行業與版塊分佈",
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

            # ------------------ 個股深度歷史趨勢 & Alpaca 實時數據整合 ------------------
            st.markdown("---")
            st.subheader("🔍 個股 1 年趨勢與 Alpaca 實時報價")
            
            selected_ticker = st.selectbox("選擇一檔已篩選個股查看詳情：", options=df_final['symbol'].tolist())
            
            if selected_ticker:
                st.markdown(f"### 🏷️ 股票資訊：{selected_ticker}")
                
                # 實時報價區
                realtime_data = None
                if alpaca_client:
                    with st.spinner("⚡ 正在透過 Alpaca 連接實時報價..."):
                        realtime_data = fetch_realtime_price_alpaca(selected_ticker, alpaca_client)
                
                if realtime_data:
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.metric(
                            label="⚡ Alpaca 實時價格 (USD)", 
                            value=f"${realtime_data['price']:.2f}",
                            help="來自 Alpaca 即時數據流"
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
                        st.info("💡 提示：若要啟用零延遲實時報價，請在左側輸入你的 Alpaca API 金鑰！")
                
                # 歷史趨勢圖
                yf_formatted = selected_ticker.replace('/', '-').replace('.', '-')
                if yf_formatted in df_prices.columns:
                    stock_series = df_prices[yf_formatted].dropna()
                    
                    fig_line = px.line(
                        x=stock_series.index,
                        y=stock_series.values,
                        title=f"{selected_ticker} - 近 1 年每日收盤價走勢",
                        labels={"x": "日期", "y": "收盤價 (USD)"}
                    )
                    fig_line.update_traces(line_color="#2563EB", line_width=2)
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    st.warning("無該股之詳細歷史價格。")
                    
# 說明欄
st.markdown("""
<div style="background-color: #EFF6FF; padding: 1.5rem; border-radius: 10px; margin-top: 2rem;">
    <h4>💡 什麼是 RS (Relative Strength) 相對強度分數？</h4>
    <p>本系統使用之 RS 分數為模擬 <b>William O'Neil (威廉·歐尼爾)</b> 創立之 MarketSmith/IBD 的 RS Rating。它將個股與<b>全市場大於指定市值、有成交量股票</b>的 1 年回報進行加權對比排名。</p>
    <ul>
        <li><b>加權分配</b>：近 3 個月表現佔 <b>40%</b>，其餘三個季度各佔 <b>20%</b>。這能更敏感地捕捉近期爆發的超級強勢領頭羊。</li>
        <li><b>評分區間 (1 - 99)</b>：分數為百分位排名。例如 <b>RS 95</b> 代表該股在過去一年的加權回報率優於市場上 <b>95%</b> 的股票。</li>
    </ul>
</div>
""", unsafe_allow_html=True)

```
