import pandas as pd
import re
import numpy as np

# ==========================================
# 1. 類別清洗
# ==========================================
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
# 2. 文字清洗
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

# ==========================================
# 3. 特徵提取 (關鍵3寶)
# ==========================================
def extract_viral_features(row):
    title = str(row['title_clean'])
    # 1. 標題長度
    title_len = len(title) if len(title) > 0 else 0
    # 2. 情緒標點計數
    punct_count = title.count('!') + title.count('！') + title.count('?') + title.count('？')
    # 3. 是否含數字
    has_digit = 1 if re.search(r'\d', title) else 0
    
    return pd.Series([title_len, punct_count, has_digit], 
                     index=['title_len', 'punct_count', 'has_digit'])

def worker_process_chunk(df_chunk):
    """Worker: 清洗 + 特徵 + 斷詞 (回傳 List)"""
    try:
        import monpa
    except ImportError:
        pass

    # 清洗
    df_chunk['category_clean'] = df_chunk['category'].apply(clean_category)
    df_chunk['title_clean'] = df_chunk['title'].apply(clean_title_strict)
    df_chunk['content_clean'] = df_chunk['content'].apply(clean_text_strict)
    
    # 過濾
    df_chunk = df_chunk.dropna(subset=['title_clean', 'content_clean', 'label'])
    df_chunk = df_chunk[df_chunk['content_clean'].str.len() > 30]
    df_chunk['label'] = pd.to_numeric(df_chunk['label'], errors='coerce').fillna(0).astype(int)
    
    # 提取特徵
    feats = df_chunk.apply(extract_viral_features, axis=1)
    df_chunk = pd.concat([df_chunk, feats], axis=1)
    
    # 斷詞 (轉為 List)
    tokens_list = []
    for text in df_chunk['title_clean']:
        try:
            words = monpa.cut(str(text))
            valid_words = [w for w in words if len(w) > 1 and w not in ['新聞', '報導', '表示', '曝光']]
            # 這裡改回 append(valid_words) 也就是列表
            tokens_list.append(valid_words)
        except:
            tokens_list.append([])
    
    df_chunk['tokens'] = tokens_list
    
    # 回傳 CSV 需要的欄位
    keep_cols = [
        'label', 'category_clean', 'title_clean', 'content_clean', 
        'title_len', 'punct_count', 'has_digit', 'tokens'
    ]
    final_cols = [c for c in keep_cols if c in df_chunk.columns]
    
    return df_chunk[final_cols]
