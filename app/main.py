import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import time
from datetime import datetime, timedelta

st.set_page_config(page_title="臨玖 - 熱力圖偵錯版", layout="wide")

# 檢測數據是否成功取得的除錯函數
def debug_heatmap(df):
    if df is None or df.empty:
        st.error("❌ 數據異常：master_df 是空的，檢查計算邏輯。")
        return
    
    st.success(f"✅ 檢測到 {len(df)} 隻股票數據，正在繪圖...")
    
    # 確保資料結構正確
    fig = px.treemap(
        df,
        path=['GICS 行業', '股票代號'],
        values='相對強度 (RS 分數)',
        color='相對強度 (RS 分數)',
        color_continuous_scale='RdYlGn',
        title="美股戰場熱力圖"
    )
    st.plotly_chart(fig, use_container_width=True)

# 測試用假數據 (如果計算邏輯暫時出錯，用呢個嚟測試個圖有無出嚟)
def get_test_data():
    return pd.DataFrame({
        'GICS 行業': ['科技', '科技', '金融', '醫療'],
        '股票代號': ['NVDA', 'AMD', 'JPM', 'LLY'],
        '相對強度 (RS 分數)': [95, 88, 70, 82],
        '最新現價 ($)': [120, 150, 200, 800]
    })

# 程式入口
st.title("🔧 熱力圖偵錯終端")

# 1. 嘗試載入真實數據 (將你原本的計算代碼放在這裡)
# master_df = ... 

# 2. 如果真實數據出錯，嘗試顯示測試數據
if 'master_df' not in locals():
    st.warning("⚠️ 真實數據尚未生成，先顯示測試圖表...")
    master_df = get_test_data()

# 3. 繪圖
debug_heatmap(master_df)
