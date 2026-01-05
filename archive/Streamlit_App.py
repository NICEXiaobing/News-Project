import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime
from inference_engine import NewsPredictor

# ==========================================
# 1. 介面設定 (Professional UI)
# ==========================================
st.set_page_config(
    page_title="熱度預測系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定義 CSS (讓介面更像商業儀表板)
st.markdown("""
    <style>
    /* 全局字體 */
    .block-container { padding-top: 2rem; }
    
    /* 標題樣式 */
    .main-title { font-size: 2.5rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.5rem; }
    .sub-title { font-size: 1.1rem; color: #64748B; margin-bottom: 2rem; }
    
    /* 卡片樣式 */
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .metric-label { font-size: 1rem; color: #64748B; font-weight: 600; }
    .metric-value { font-size: 2.2rem; font-weight: 800; color: #0F172A; }
    
    /* 燈號樣式 */
    .traffic-light {
        font-size: 4rem;
        margin: 0 auto;
        line-height: 1;
        text-shadow: 0 0 20px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 載入 AI 引擎
# ==========================================
@st.cache_resource
def load_engine():
    return NewsPredictor() # 已經強制使用 CPU，不會崩潰

try:
    predictor = load_engine()
except Exception as e:
    st.error(f"系統初始化失敗: {e}")
    st.stop()

# ==========================================
# 3. 側邊欄 (設定區)
# ==========================================
with st.sidebar:
    st.header("⚙️ 系統參數")
    threshold = st.slider("熱度判定門檻 (Threshold)", 0.0, 1.0, 0.50, 0.01)
    
    st.markdown("---")
    st.markdown("### 📅 發布時間模擬")
    pub_date = st.date_input("日期", datetime.now())
    pub_time = st.time_input("時間", datetime.now())
    publish_dt = datetime.combine(pub_date, pub_time)
    
    st.info("模式：穩定 (CPU)\n模型：Stacking Ensemble")

# ==========================================
# 4. 主畫面佈局
# ==========================================
st.markdown('<div class="main-title">熱度預測系統</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">AI 驅動的新聞擴散力分析儀表板</div>', unsafe_allow_html=True)

# 使用兩欄佈局：左邊輸入，右邊顯示結果
col_left, col_right = st.columns([4, 6], gap="large")

with col_left:
    st.markdown("### 📝 新聞資料輸入")
    with st.container(border=True):
        news_title = st.text_input("新聞標題", placeholder="請輸入完整標題...", max_chars=100)
        news_content = st.text_area("新聞內文", placeholder="請輸入新聞內文 (建議至少 50 字)...", height=350)
        
        btn_analyze = st.button("開始分析 (Analyze)", type="primary", use_container_width=True)

# 變數初始化 (用於存放結果)
result_prob = None
result_light = None
result_emotions = None

# ==========================================
# 5. 分析邏輯
# ==========================================
if btn_analyze:
    if not news_title or not news_content:
        st.toast("⚠️ 請填寫標題與內文", icon="⚠️")
    else:
        with st.spinner("🤖 AI 正在進行多維度分析 (情緒 + 語意 + 結構)..."):
            # 執行預測
            prob, feats = predictor.predict(news_title, news_content, publish_dt)
            result_prob = prob
            
            # --- 燈號邏輯 ---
            # 紅燈：機率 >= 門檻 (熱門)
            # 黃燈：門檻 > 機率 >= 門檻*0.8 (潛力)
            # 綠燈：機率 < 門檻*0.8 (一般)
            if prob >= threshold:
                result_light = ("🔴", "高熱度 (High Viral)", "#EF4444")
            elif prob >= (threshold * 0.8):
                result_light = ("🟡", "潛在熱度 (Potential)", "#F59E0B")
            else:
                result_light = ("🟢", "一般新聞 (Normal)", "#10B981")

            # --- 情緒解析 ---
            # 提取 prob_ 開頭的特徵
            emo_dict = {k.replace('prob_', '').replace('feel_', ''): v for k, v in feats.items() if k.startswith('prob_')}
            # 排序取前三
            result_emotions = sorted(emo_dict.items(), key=lambda x: x[1], reverse=True)[:3]

# ==========================================
# 6. 結果顯示區 (右欄)
# ==========================================
with col_right:
    st.markdown("### 📊 分析結果報告")
    
    if result_prob is None:
        # 尚未分析時的佔位符
        st.info("👈 請在左側輸入新聞內容並點擊「開始分析」")
    else:
        # 第一排：燈號與機率 (Metric Cards)
        c1, c2 = st.columns(2)
        
        with c1:
            icon, status_text, color = result_light
            st.markdown(f"""
                <div class="metric-card" style="border-top: 5px solid {color};">
                    <div class="metric-label">熱度燈號</div>
                    <div class="traffic-light">{icon}</div>
                    <div style="color: {color}; font-weight: bold; margin-top: 10px;">{status_text}</div>
                </div>
            """, unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"""
                <div class="metric-card" style="border-top: 5px solid #3B82F6;">
                    <div class="metric-label">成為熱門機率</div>
                    <div class="metric-value">{result_prob*100:.1f}%</div>
                    <div style="font-size: 0.9rem; color: #94A3B8;">判定門檻: {threshold*100:.0f}%</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        
        # 第二排：情緒分析 (Progress Bars)
        st.markdown("#### 🎭 讀者情緒預測 (Top 3)")
        
        # 情緒中翻英對照 (讓介面更親民)
        emo_trans = {
            'angry': '憤怒 / 爭議', 'happy': '開心 / 正面', 'sad': '難過 / 遺憾',
            'fear': '恐懼 / 擔憂', 'surprise': '驚訝 / 震撼', 'odd': '新奇 / 怪異',
            'boring': '無聊 / 平淡', 'warm': '溫馨 / 感人', 'worried': '焦慮', 'informative': '實用'
        }
        
        for emo_name, score in result_emotions:
            cn_name = emo_trans.get(emo_name, emo_name.capitalize())
            col_label, col_bar, col_val = st.columns([2, 6, 1])
            with col_label:
                st.write(f"**{cn_name}**")
            with col_bar:
                st.progress(score)
            with col_val:
                st.write(f"{score*100:.0f}%")

        # 第三排：關鍵結構指標
        with st.expander("🔍 查看詳細結構指標"):
            k1, k2, k3 = st.columns(3)
            k1.metric("MacBERT 語意分", f"{feats['macbert_score']:.3f}")
            k2.metric("標題情緒標點", f"{feats['punct_count']} 個")
            k3.metric("標題長度", f"{feats['title_len']} 字")