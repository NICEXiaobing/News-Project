import pandas as pd
import re
import numpy as np

# ==========================================
# 1. 斷詞 Worker (給程式一用)
# ==========================================
def worker_tokenization_task(df_chunk):
    """
    輸入: 包含 'title_clean' 的 DataFrame chunk
    輸出: 新增 'tokens_str' 欄位的 DataFrame chunk
    """
    # 延遲匯入 monpa，避免多核心卡死
    try:
        import monpa
    except ImportError:
        pass

    token_str_list = []
    
    # 防呆：確保轉為字串
    titles = df_chunk['title_clean'].astype(str)
    
    for text in titles:
        try:
            # 1. 斷詞
            words = monpa.cut(text)
            # 2. 過濾短詞與停用詞
            valid_words = [w for w in words if len(w) > 1 and w not in ['新聞', '報導', '表示', '曝光', '今日']]
            # 3. 接成空白分隔字串
            token_str_list.append(" ".join(valid_words))
        except:
            token_str_list.append("")
    
    df_chunk['tokens_str'] = token_str_list
    return df_chunk

# ==========================================
# 2. 數值特徵提取 (給程式二用，若需要現場算)
# ==========================================
def extract_viral_features(row):
    title = str(row['title_clean'])
    return pd.Series([
        len(title) if len(title) > 0 else 0, # title_len
        title.count('!') + title.count('！') + title.count('?') + title.count('？'), # punct_count
        1 if re.search(r'\d', title) else 0 # has_digit
    ], index=['title_len', 'punct_count', 'has_digit'])
