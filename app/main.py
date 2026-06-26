import streamlit as st
# 修正路徑：因為 Streamlit 執行時已經喺 app 資料夾內，所以直接由 views 引入就可以！
from views.watchlist import load_view

# 1. 網頁全域基本設定
st.set_page_config(
    page_title="美股自動化雷達系統",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 建立側邊欄導航 (Sidebar)
st.sidebar.title("🧭 雷達導航中心")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "選擇功能分頁", 
    ["📈 動態觀測雷達"]
)

# 3. 根據側邊欄的選擇，渲染對應的畫面
if page == "📈 動態觀測雷達":
    load_view()
