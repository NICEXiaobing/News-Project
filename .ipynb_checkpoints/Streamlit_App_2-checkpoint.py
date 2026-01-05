import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime
from inference_engine import NewsPredictor

# ==========================================
# 1. 商業級視覺設計 (Professional UI/UX)
# ==========================================
st.set_page_config(
    page_title="News Viral Lens | 新聞熱度透視鏡",
    page_icon="🔮",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 高級 CSS：修正輸入框顏色、高對比度
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Noto+Sans+TC:wght@400;500;700&display=swap');
    
    /* 全域設定 */
    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
        background-color: #F8FAFC; /* 淺灰背景 */
        color: #0F172A; /* 深黑字體 */
    }
    
    #MainMenu, footer, header {visibility: hidden;}
    
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
    }
    
    /* --- 1. 頂部導覽列 --- */
    .navbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 1.5rem;
        background: white;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin-bottom: 2rem;
    }
    .brand { font-size: 1.1rem; font-weight: 700; color: #0F172A; display: flex; align-items: center; gap: 8px; }
    .sys-status { font-size: 0.75rem; background: #ECFDF5; color: #047857; padding: 4px 10px; border-radius: 99px; font-weight: 600; border: 1px solid #A7F3D0; }

    /* --- 2. Streamlit 原生容器美化 --- */
    [data-testid="stBorderDomWrapper"] {
        background-color: white;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #E2E8F0;
        padding: 1.5rem;
    }
    
    /* --- 3. 輸入框優化 (關鍵修正：字體顏色與背景) --- */
    /* 強制設定輸入框內部文字顏色為全黑，背景為全白 */
    .stTextInput input, .stTextArea textarea {
        background-color: #FFFFFF !important; 
        color: #000000 !important;
        border-radius: 8px;
        border: 1px solid #94A3B8; /* 加深邊框顏色 */
        padding: 10px 12px;
        font-size: 1rem;
        caret-color: #3B82F6; /* 游標顏色 */
    }
    
    /* 輸入框 focus 狀態 */
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
    }
    
    /* 輸入框的 Label 顏色 */
    .stTextInput label, .stTextArea label {
        color: #1E293B !important;
        font-weight: 600;
    }

    /* 提示文字 (Caption) */
    .input-hint {
        font-size: 0.85rem;
        color: #64748B;
        margin-bottom: 5px;
        display: flex;
        align-items: center;
        gap: 5px;
    }
    
    /* --- 4. 主按鈕 --- */
    .stButton > button {
        width: 100%;
        height: 50px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 1rem;
        background: #0F172A;
        border: none;
        color: white;
        transition: all 0.2s;
        margin-top: 10px;
    }
    .stButton > button:hover {
        background: #334155;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
        transform: translateY(-1px);
    }

    /* --- 5. HTML 儀表板組件樣式 (CSS) --- */
    .dashboard-card {
        background: white;
        border-radius: 20px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        overflow: hidden;
        border: 1px solid #E2E8F0;
        margin-top: 1.5rem;
        font-family: 'Inter', sans-serif;
    }
    
    .dashboard-header {
        padding: 2.5rem 2rem 1.5rem 2rem;
        text-align: center;
        background: linear-gradient(to bottom, #FFFFFF, #F8FAFC);
        border-bottom: 1px solid #F1F5F9;
    }

    .dashboard-body {
        padding: 2rem;
    }
    
    .score-ring {
        position: relative;
        width: 160px;
        height: 160px;
        margin: 0 auto 1.5rem auto;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        background: white;
        border-radius: 50%;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
    }
    .score-val { font-size: 4rem; font-weight: 800; line-height: 1; letter-spacing: -2px; }
    .score-lbl { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 700; color: #64748B; margin-top: 8px; }

    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 20px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 1rem;
        letter-spacing: 0.5px;
    }

    .metric-row {
        display: flex;
        align-items: center;
        margin-bottom: 16px;
    }
    .metric-label {
        width: 120px;
        font-size: 0.95rem;
        font-weight: 600;
        color: #1E293B;
        text-align: right;
        padding-right: 15px;
    }
    .metric-bar-container {
        flex-grow: 1;
        height: 8px;
        background: #F1F5F9;
        border-radius: 4px;
        overflow: hidden;
    }
    .metric-value {
        width: 50px;
        text-align: right;
        font-size: 0.95rem;
        font-weight: 700;
        color: #0F172A;
        padding-left: 10px;
    }
    
    .analysis-box {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1rem;
        text-align: left;
    }
    .priority-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-bottom: 8px;
        text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 系統初始化
# ==========================================
@st.cache_resource
def load_engine():
    return NewsPredictor()

try:
    predictor = load_engine()
except Exception as e:
    st.error(f"System Error: {e}")
    st.stop()

# ==========================================
# 3. 介面結構
# ==========================================
st.markdown("""
    <div class="navbar">
        <div class="brand">
            <span>🔮</span> Viral Lens <span style="color:#94A3B8;">Analytics</span>
        </div>
        <div class="sys-status">● System Online</div>
    </div>
""", unsafe_allow_html=True)

# 輸入區塊
with st.container(border=True):
    # 標題區塊 Header
    st.markdown("<div style='font-size:0.9rem; font-weight:700; color:#64748B; margin-bottom:15px; text-transform:uppercase; border-bottom:1px solid #E2E8F0; padding-bottom:10px;'>Input Source / 資料輸入</div>", unsafe_allow_html=True)
    
    # 1. Title Input
    st.markdown("**📌 新聞標題 (News Title)**")
    st.caption("💡 提示：建議輸入完整標題，包含標點符號（如：！、？）能提升情緒判讀準確度。")
    news_title = st.text_input("Title", placeholder="範例：震驚！颱風假有望？氣象署最新回應...", max_chars=80, label_visibility="collapsed")
    
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
    
    # 2. Content Input
    st.markdown("**📝 新聞內文 (News Content)**")
    st.caption("💡 提示：請貼上至少 50 字的新聞前段或全文摘要，AI 將分析語意結構。")
    news_content = st.text_area("Content", placeholder="請在此貼上新聞內容...", height=150, label_visibility="collapsed")
    
    # 3. Advanced Settings
    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
    with st.expander("⚙️ 進階參數 (發布時間模擬)", expanded=False):
        c1, c2 = st.columns(2)
        pub_date = c1.date_input("預計發布日期", datetime.now())
        pub_time = c2.time_input("預計發布時間", datetime.now())

st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
btn_analyze = st.button("開始分析 (Start Analysis)")

# ==========================================
# 4. 分析邏輯與渲染 (絕對修正版)
# ==========================================
if btn_analyze:
    if not news_title or not news_content:
        st.toast("請輸入標題與內文", icon="⚠️")
    else:
        publish_dt = datetime.combine(pub_date, pub_time)
        with st.spinner("正在進行多維度風險評估..."):
            time.sleep(0.6)
            prob, feats = predictor.predict(news_title, news_content, publish_dt)
            
            # --- 數據準備 ---
            score = int(prob * 100)
            
            # 專業分析邏輯
            if score >= 80:
                color = "#DC2626"
                bg_pill = "#FEF2F2"
                text_status = "⚠️ 高度擴散預警"
                priority_tag = "P0 - 最高優先"
                tag_bg = "#FECACA"
                tag_color = "#991B1B"
                analysis_html = """<strong>• 擴散風險評估：</strong>此內容具備極強的病毒式傳播特徵，預計在短時間內引發大量轉發。<br><br><strong>• 查核建議：</strong>建議<strong>立即進行事實查核</strong>。高情緒強度的內容常伴隨輿論極化風險。<br><br><strong>• 監控策略：</strong>需啟動即時輿情監控，特別留意留言區的情緒升溫跡象。"""
            elif score >= 50:
                color = "#D97706"
                bg_pill = "#FFFBEB"
                text_status = "⚡️ 潛在熱點話題"
                priority_tag = "P1 - 密切關注"
                tag_bg = "#FDE68A"
                tag_color = "#92400E"
                analysis_html = """<strong>• 擴散風險評估：</strong>內容具備話題性，可能在特定社群產生共鳴。<br><br><strong>• 查核建議：</strong>建議確認關鍵數據與引用來源的正確性，避免誤導性標題。<br><br><strong>• 監控策略：</strong>排程定期回顧熱度變化，觀察是否進入黃金擴散期。"""
            else:
                color = "#059669"
                bg_pill = "#ECFDF5"
                text_status = "🍵 常態資訊流"
                priority_tag = "P2 - 一般監控"
                tag_bg = "#A7F3D0"
                tag_color = "#065F46"
                analysis_html = """<strong>• 擴散風險評估：</strong>屬性偏向客觀陳述或分眾資訊，大規模擴散機率低。<br><br><strong>• 查核建議：</strong>依照標準作業程序（SOP）進行例行性審視即可。<br><br><strong>• 監控策略：</strong>無需特別介入，作為常態內容發布。"""

            emo_map = {
                'angry': '憤怒 / 爭議', 'happy': '正面 / 開心', 'sad': '悲傷 / 遺憾',
                'fear': '恐懼 / 擔憂', 'surprise': '驚訝 / 震撼', 'odd': '新奇 / 怪異',
                'boring': '平淡 / 無感', 'warm': '溫馨 / 感人', 'worried': '焦慮 / 緊張', 'informative': '實用 / 資訊'
            }
            emo_dict = {k.replace('prob_', '').replace('feel_', ''): v for k, v in feats.items() if k.startswith('prob_')}
            top_emos = sorted(emo_dict.items(), key=lambda x: x[1], reverse=True)[:3]

            # ==================================================================
            # 🔥 HTML 渲染核心 (使用單行拼接，100% 防止縮排錯誤)
            # ==================================================================
            
            # 1. 構建情緒分析 HTML
            metrics_html = ""
            for emo_key, val in top_emos:
                label = emo_map.get(emo_key, "一般")
                pct = int(val * 100)
                # 使用單行字串拼接，不換行，避免任何縮排問題
                metrics_html += f'<div class="metric-row"><div class="metric-label">{label}</div><div class="metric-bar-container"><div style="width: {pct}%; height: 100%; background: {color}; border-radius: 4px;"></div></div><div class="metric-value">{pct}%</div></div>'

            # 2. 構建完整 HTML 儀表板 (分段拼接，確保無縮排)
            html_parts = []
            html_parts.append(f'<div class="dashboard-card">')
            
            # Header
            html_parts.append(f'<div class="dashboard-header">')
            html_parts.append(f'<div class="score-ring" style="border: 4px solid {color};"><div class="score-val" style="color: {color};">{score}</div><div class="score-lbl">Viral Score</div></div>')
            html_parts.append(f'<div class="status-badge" style="background: {bg_pill}; color: {color}; border: 1px solid {color}40;">{text_status}</div>')
            html_parts.append(f'</div>') # End Header
            
            # Body
            html_parts.append(f'<div class="dashboard-body">')
            html_parts.append(f'<div style="margin-bottom: 1.5rem;"><div style="font-size: 0.85rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; margin-bottom: 1rem; letter-spacing: 1px;">Detected Sentiment / 情緒成分分析</div>{metrics_html}</div>')
            
            # Analysis Box
            html_parts.append(f'<div class="analysis-box" style="border-left: 4px solid {color};">')
            html_parts.append(f'<div style="display:flex; align-items:center; gap:8px; font-size:0.9rem; font-weight:700; color:#334155; margin-bottom:12px; text-transform:uppercase;"><span style="font-size:1.1rem;">🛡️</span> 熱度風險與查核策略</div>')
            html_parts.append(f'<div style="margin-bottom: 8px;"><span class="priority-tag" style="background:{tag_bg}; color:{tag_color};">{priority_tag}</span></div>')
            html_parts.append(f'<div style="font-size: 0.95rem; line-height: 1.6; color: #334155;">{analysis_html}</div>')
            html_parts.append(f'</div>') # End Analysis Box
            
            html_parts.append(f'</div>') # End Body
            html_parts.append(f'</div>') # End Card

            # 3. 組合並渲染
            final_html = "".join(html_parts)
            st.markdown(final_html, unsafe_allow_html=True)