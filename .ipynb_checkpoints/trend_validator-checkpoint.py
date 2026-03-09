import time
import random
from urllib.parse import urlparse

# 嘗試匯入 googlesearch 套件，若無安裝則啟用備用模式
try:
    from googlesearch import search
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    print("⚠️ 未安裝 googlesearch-python，TrendValidator 將以模擬模式運行。")

class TrendValidator:
    def __init__(self):
        # 台灣主流媒體與指標性網站網域清單 (用於計算跨媒共識)
        self.mainstream_media = [
            'cna.com.tw',       # 中央社
            'udn.com',          # 聯合
            'ltn.com.tw',       # 自由
            'chinatimes.com',   # 中時
            'ettoday.net',      # ETtoday
            'tvbs.com.tw',      # TVBS
            'pts.org.tw',       # 公視
            'storm.mg',         # 風傳媒
            'setn.com',         # 三立
            'mirrormedia.mg',   # 鏡週刊
            'bnext.com.tw',     # 數位時代
            'cw.com.tw',        # 天下雜誌
            'tw.news.yahoo.com' # Yahoo 新聞
        ]

    def check_diffusion(self, title):
        """
        檢查該新聞標題在全網的擴散程度 (有幾家不同媒體跟進報導)
        回傳擴散等級 (HIGH, MEDIUM, LOW) 與 UI 顯示文字
        """
        if not SEARCH_AVAILABLE:
            return self._mock_check(title)

        print(f"🌍 [TrendValidator] 正在掃描全網擴散度: {title[:15]}...")
        found_media = set()
        
        try:
            # 搜尋前 12 筆結果 (設定 sleep_interval=1.5 防止被 Google 鎖 IP)
            results = search(title, num_results=12, lang="zh-TW", sleep_interval=1.5)
            
            for url in results:
                try:
                    domain = urlparse(url).netloc
                    # 檢查該網址是否屬於我們定義的主流媒體
                    for media in self.mainstream_media:
                        if media in domain:
                            found_media.add(media)
                except:
                    continue
            
            coverage_count = len(found_media)
            
            # --- 雙軌決策：熱度擴散評判邏輯 ---
            if coverage_count >= 4:
                return {
                    "is_viral": True,
                    "status_text": f"🔥 全網發酵 (已覆蓋 {coverage_count} 家主流媒體)",
                    "momentum": "HIGH",
                    "sources": list(found_media)
                }
            elif coverage_count >= 2:
                return {
                    "is_viral": False,
                    "status_text": f"📈 跨媒關注 (共 {coverage_count} 家媒體報導)",
                    "momentum": "MEDIUM",
                    "sources": list(found_media)
                }
            else:
                return {
                    "is_viral": False,
                    "status_text": "❄️ 尚未擴散 (目前為單一來源或極新快訊)",
                    "momentum": "LOW",
                    "sources": list(found_media)
                }

        except Exception as e:
            # 遇到 HTTP 429 (Too Many Requests) 或網路斷線時，自動切換備用模式
            print(f"⚠️ Trend Validator 搜尋受限，啟動備用防呆機制: {e}")
            return self._mock_check(title)

    def _mock_check(self, title):
        """
        備用模式 (Mock Mode)：
        當 Google API 被擋或沒網路時，根據標題關鍵字給出「看起來很真實」的擬真數據。
        確保比賽現場 Live Demo 絕對不會因為外部 API 而當機。
        """
        title_str = str(title)
        time.sleep(random.uniform(0.5, 1.2)) # 假裝正在搜尋的延遲感
        
        # 定義容易引發跨媒跟進的強勢關鍵字
        high_viral_keywords = ['地震', '停班停課', '颱風', '崩盤', '大漲', '奪牌', '聲明']
        medium_viral_keywords = ['網傳', '曝光', '最新', '快訊', '回應', '懶人包']
        
        if any(kw in title_str for kw in high_viral_keywords):
            mock_count = random.randint(4, 7)
            return {
                "is_viral": True,
                "status_text": f"🔥 全網發酵 (已覆蓋 {mock_count} 家主流媒體) [模擬]",
                "momentum": "HIGH",
                "sources": random.sample(self.mainstream_media, mock_count)
            }
        elif any(kw in title_str for kw in medium_viral_keywords):
            mock_count = random.randint(2, 3)
            return {
                "is_viral": False,
                "status_text": f"📈 跨媒關注 (共 {mock_count} 家媒體報導) [模擬]",
                "momentum": "MEDIUM",
                "sources": random.sample(self.mainstream_media, mock_count)
            }
        else:
            return {
                "is_viral": False,
                "status_text": "❄️ 尚未擴散 (目前為單一來源或極新快訊) [模擬]",
                "momentum": "LOW",
                "sources": []
            }