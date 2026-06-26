import streamlit as st
import pandas as pd
import plotly.express as px
# ... (其他 import 維持不變)

# 替換原有的 st.dataframe 部分，改成以下代碼：

if not filtered_df.empty:
    st.success(f"🎉 掃描完畢！共有 {len(filtered_df)} 隻強勢股：")
    
    # 🌟 核心：整作熱力矩陣 (Treemap)
    fig = px.treemap(
        filtered_df, 
        path=['GICS 行業', '股票代號'], 
        values='相對強度 (RS 分數)',      # 方塊大小取決於強度
        color='相對強度 (RS 分數)',        # 顏色深淺取決於強度
        color_continuous_scale='RdYlGn', # 紅黃綠配色
        hover_data=['最新現價 ($)', '三級火箭動能'],
        title="美股強勢股分佈熱力圖 (Heatmap)"
    )
    
    fig.update_layout(margin=dict(t=50, l=25, r=25, b=25))
    st.plotly_chart(fig, use_container_width=True)
    
    # 如果你重想留低個列表，可以加番呢句
    with st.expander("查看原始詳細數據列表"):
        st.dataframe(filtered_df, use_container_width=True)
else:
    st.info("⚠️ 當前篩選條件下，暫無標的達標。")
