import monpa
import re

def clean_text(text):
    """簡單的文字清洗"""
    if not isinstance(text, str):
        return ""
    # 移除 HTML 標籤
    text = re.sub(r'<[^>]+>', '', text)
    # 移除多餘空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def monpa_cut_wrapper(text):
    """
    Monpa 斷詞包裝函式 (放在這裡子進程才讀得到)
    """
    try:
        # 使用 monpa.cut 進行斷詞，並以空白分隔回傳字串
        words = list(monpa.cut(text))
        return " ".join(words)
    except Exception as e:
        return ""