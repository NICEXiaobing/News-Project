import pandas as pd
import re
import numpy as np

# 嘗試匯入 monpa
try:
    import monpa
except ImportError:
    monpa = None

# ==========================================
# 1. 清洗邏輯
# ==========================================
GARBAGE_PATTERNS = [
    r'👉.*', r'更多新聞：.*', r'更多新聞:.*', r'延伸閱讀：.*', r'【延伸閱讀】.*',
    r'更多鏡週刊報導', r'看更多.*', r'→.*', r'外稿 #.*', r'點我下載.*?APP', 
    r'加入.*?LINE好友', r'http\S+', r'<.*?>'
]

def clean_text_strict(text):
    if pd.isna(text): return ""
    text = str(text)
    for p in GARBAGE_PATTERNS:
        text = re.sub(p, '', text, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip()

def clean_title_strict(text):
    if pd.isna(text): return ""
    text = str(text)
    text = re.sub(r'[│|-]\s*TVBS.*', '', text)
    text = re.sub(r'[│|-]\s*聯合新聞網.*', '', text)
    text = re.sub(r'[│|-]\s*ETtoday.*', '', text)
    return text.strip()

def clean_category(cat):
    if pd.isna(cat): return "其他"
    c = str(cat).lower().strip()
    if any(x in c for x in ['politic', '政治', 'vote', '選舉', '立委', '政黨']): return '政治'
    if any(x in c for x in ['social', 'society', '社會', 'local', 'crime', '刑案']): return '社會'
    if any(x in c for x in ['life', 'style', 'living', '生活', 'health', '健康', 'food', '美食', 'travel', '旅遊', '氣象']): return '生活'
    if any(x in c for x in ['ent', 'star', 'celebrity', 'movie', 'music', '娛樂', '影劇', '明星']): return '娛樂'
    if any(x in c for x in ['sport', 'nba', 'mlb', 'gym', '體育', '運動', '棒球', '籃球']): return '體育'
    if any(x in c for x in ['global', 'world', 'intl', 'china', 'us', '國際', '兩岸', '全球']): return '國際'
    if any(x in c for x in ['financ', 'money', 'business', 'stock', 'market', '財經', '經濟', '股市', '房產']): return '財經'
    if any(x in c for x in ['tech', '3c', 'science', 'mobile', 'app', 'ai', '科技', '科學', '電玩']): return '科技'
    if any(x in c for x in ['news', 'focus', 'latest', '即時', '焦點', '快訊']): return '即時'
    return "其他"

# ==========================================
# 2. Worker 主程式
# ==========================================
def worker_process_chunk(df_chunk):
    # A. 基礎清洗
    df_chunk['category_clean'] = df_chunk['category'].apply(clean_category)
    df_chunk['title_clean'] = df_chunk['title'].apply(clean_title_strict)
    df_chunk['content_clean'] = df_chunk['content'].apply(clean_text_strict)
    
    # 過濾無效資料
    df_chunk = df_chunk.dropna(subset=['title_clean', 'content_clean'])
    df_chunk = df_chunk[df_chunk['title_clean'] != '']
    
    # B. 結構特徵提取 (Model Input)
    df_chunk['title_len'] = df_chunk['title_clean'].apply(lambda x: len(str(x)))
    df_chunk['punct_count'] = df_chunk['title_clean'].apply(lambda x: str(x).count('!') + str(x).count('！') + str(x).count('?') + str(x).count('？'))
    df_chunk['has_digit'] = df_chunk['title_clean'].apply(lambda x: 1 if re.search(r'\d', str(x)) else 0)

    # C. Monpa 斷詞 (For EDA Only)
    def cut_sentence(text):
        if not monpa: return str(text)
        try:
            return " ".join(monpa.cut(str(text)))
        except:
            return ""
            
    df_chunk['tokens'] = df_chunk['title_clean'].apply(cut_sentence)
    
    return df_chunk
