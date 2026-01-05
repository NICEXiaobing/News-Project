#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ===============================================================
#
#   九合一新聞爬蟲 (CNA, UDN, SETN, TVBS, EBC, NOWnews, ETtoday, LTN, ChinaTimes)
#   版本: v11 (2025-10-28)
#
#   - 最終版：完全移除 `credibility_label` 欄位，以匹配您手動修改後的 7 欄位 CSV。
#   - 保留 `news_snapshot_log.csv` 檔案的 "附加 (Append)" 模式。
#   - 修正 ChinaTimes 爬蟲邏輯。
#   - 強化 Crontab 穩定性 (絕對路徑, Logging)。
#
# ===============================================================

# ===============================================================
# Cell 1: 環境設定、全域變數與路徑
# ===============================================================
import sys
import subprocess
import importlib
import logging
import os
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
import time
import lxml

# --- 設定路徑 ---
# 讓腳本在 crontab 中也能正確找到檔案
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd() 

# *** 這是您的主要資料庫，腳本會「附加」到此檔案 ***
DB_FILENAME = os.path.join(BASE_DIR, 'News_dataset.csv')
TEMP_JSON_FILENAME = os.path.join(BASE_DIR, 'temp_all_headlines.json')
LOG_FILENAME = os.path.join(BASE_DIR, 'scraper.log') # 所有的執行紀錄會存在這裡

# --- 設定日誌 ---
logger = logging.getLogger()
logger.setLevel(logging.INFO) 
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')

if not logger.hasHandlers():
    file_handler = logging.FileHandler(LOG_FILENAME, encoding='utf-8', mode='a') 
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

# --- 全域變數 ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
}

# *** 欄位已更新：現在是 7 個欄位 ***
COLUMNS = [
    'url', 
    'title', 
    'content', 
    'source',
    'published_at', 
    'scraped_at', 
    'headline_level'
]

# 要移除的常見垃圾文字
JUNK_PATTERNS = re.compile(
    r'延伸閱讀|相關新聞|看更多|點我下載|▲|▼|'
    r'（圖／.*(提供|翻攝)）|'
    r'★.*?Disclaimer.*?★|'
    r'下載APP|'
    r'※.*?提醒您.*?※|'
    r'《.*?》提醒您|'
    r'★.*?關心您.*?★|'
    r'記者.*?／.*?報導|'
    r'編輯.*?／.*?報導'
)

# ===============================================================
# Cell 2: 環境設定
# ===============================================================
def setup_environment():
    """
    檢查並安裝所有必要的 Python 套件。
    """
    packages = [
        ('requests', 'requests'),
        ('beautifulsoup4', 'bs4'),
        ('pandas', 'pandas'),
        ('lxml', 'lxml')
    ]
    logging.info("--- 正在檢查並安裝必要套件 ---")
    
    all_installed = True
    for pkg_name, import_name in packages:
        try:
            importlib.import_module(import_name)
            logging.info(f"✅ {pkg_name} (導入名: {import_name}) 已正確導入。")
        except ImportError:
            all_installed = False
            logging.warning(f"--- 正在安裝 {pkg_name} ---")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_name])
                logging.info(f"✅ {pkg_name} 安裝完成！")
            except subprocess.CalledProcessError as e:
                logging.error(f"🔥 安裝 {pkg_name} 失敗: {e}")
                logging.error("請手動在您的終端機執行: pip install requests beautifulsoup4 pandas lxml")
                sys.exit(1)

    if all_installed:
        logging.info("\n🎉 所有必要的套件都已準備就緒！")
    else:
        logging.info("\n🎉 套件安裝完成！")

# ===============================================================
# Cell 3: 輔助函式
# ===============================================================
def get_soup(url):
    """輔助函式：發送請求並取得 BeautifulSoup 物件"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status() 
        return BeautifulSoup(response.text, 'lxml')
    except requests.RequestException as e:
        logging.warning(f"🟡 抓取 {url} 失敗: {e}")
        return None

def normalize_url(base_url, link):
    """輔助函式：將相對路徑 URL 轉換為絕對路徑"""
    if not link:
        return None
    link = link.strip() 
    if link.startswith('//'):
        return 'https:' + link
    if link.startswith('/'):
        return base_url.rstrip('/') + link
    if link.startswith('http'):
        return link
    if not link.startswith('http'):
        return base_url.rstrip('/') + '/' + link.lstrip('/')
    return link

def safe_find_text(soup, selector, default='N/A'):
    """輔助函式：安全地尋找元素並取得文字，若找不到則回傳預設值"""
    if not soup:
        return default
    element = soup.select_one(selector)
    if element:
        return element.get_text(separator='\n', strip=True)
    return default

def get_current_utc_time():
    """取得目前 UTC+8 (台灣時間) 的時間字串"""
    taiwan_tz = timezone(timedelta(hours=8))
    return datetime.now(taiwan_tz).strftime("%Y-%m-%d %H:%M:%S.%f")

def remove_duplicates(headlines):
    """移除重複的頭條，保留 URL 唯一，並優先取等級 (level) 最高的"""
    if not headlines: 
        return []
    
    df = pd.DataFrame(headlines)
    df = df.sort_values('headline_level', ascending=False)
    df_unique = df.drop_duplicates(subset=['url', 'title'], keep='first')
    df_unique = df_unique.drop_duplicates(subset=['url'], keep='first')
    
    return df_unique.to_dict('records')

def clean_content(text):
    """
    清理內文，移除常見的廣告、導覽列和圖片註解。
    """
    if text == 'N/A' or not text:
        return 'N/A'
    
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if JUNK_PATTERNS.search(line):
            continue
        if len(line) < 15: 
            continue
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()

def scrape_article_content_base(url, content_selector, time_selector):
    """
    抓取文章內文的通用基礎函式 (僅抓取內容和時間)
    """
    soup = get_soup(url)
    if not soup:
        return 'N/A', get_current_utc_time()
    
    content = safe_find_text(soup, content_selector, default='N/A')
    published_at = safe_find_text(soup, time_selector, default=get_current_utc_time()) 
    
    published_at = re.sub(r'^(發布時間|更新時間)：', '', published_at).strip()
    
    match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2})', published_at)
    if match:
        published_at = match.group(1).replace('/', '-')
    else:
        published_at = get_current_utc_time()
            
    return content, published_at

# ===============================================================
# Cell 4: Part 1 - 抓取所有網站的頭條新聞 (函式定義)
# ===============================================================

def fetch_cna_headlines():
    """(1/9) 抓取中央社 (CNA) 頭條"""
    logging.info("--- (1/9) 正在抓取 CNA 中央社頭條 ---")
    base_url = 'https://www.cna.com.tw'
    soup = get_soup(base_url) 
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div.main-idx-row.top-news div.box-title a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'www.cna.com.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'CNA'})
        except Exception as e:
            logging.warning(f"🟡 CNA Level 3 剖析錯誤: {e}")
    for item in soup.select('div.main-idx-row.major-news div.box-title a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'www.cna.com.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'CNA'})
        except Exception as e:
            logging.warning(f"🟡 CNA Level 2 剖析錯誤: {e}")
    for item in soup.select('div.main-idx-row.instant-news div.box-title a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'www.cna.com.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'CNA'})
        except Exception as e:
            logging.warning(f"🟡 CNA Level 1 剖析錯誤: {e}")
    logging.info(f"💡 CNA 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_udn_headlines():
    """(2/9) 抓取聯合新聞網 (UDN) 頭條"""
    logging.info("--- (2/9) 正在抓取 UDN 聯合新聞網頭條 ---")
    base_url = 'https://udn.com'
    soup = get_soup(base_url + '/news/breaknews/1') 
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div.context-box__content--main h2 a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'udn.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'UDN'})
        except Exception as e:
            logging.warning(f"🟡 UDN Level 2 剖析錯誤: {e}")
    for item in soup.select('div.story-list__news div.story-list__info h2 a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'udn.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'UDN'})
        except Exception as e:
            logging.warning(f"🟡 UDN Level 1 剖析錯誤: {e}")
    logging.info(f"💡 UDN 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_setn_headlines():
    """(3/9) 抓取三立新聞網 (SETN) 頭條"""
    logging.info("--- (3/9) 正在抓取 SETN 三立新聞網頭條 ---")
    base_url = 'https://www.setn.com'
    soup = get_soup(base_url)
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div.focus_news div.captionText a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'setn.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'SETN'})
        except Exception as e:
            logging.warning(f"🟡 SETN Level 3 剖析錯誤: {e}")
    for item in soup.select('div.top-hot-list li a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'setn.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'SETN'})
        except Exception as e:
            logging.warning(f"🟡 SETN Level 2 剖析錯誤: {e}")
    for item in soup.select('div.immediate-news-area div.news-list li a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'setn.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'SETN'})
        except Exception as e:
            logging.warning(f"🟡 SETN Level 1 剖析錯誤: {e}")
    logging.info(f"💡 SETN 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_tvbs_headlines():
    """(4/9) 抓取 TVBS 新聞網頭條"""
    logging.info("--- (4/9) 正在抓取 TVBS 新聞網頭條 ---")
    base_domain = 'https://www.tvbs.com.tw' 
    soup = get_soup(base_domain) 
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div.hero_main a.swiper-slide'):
        try:
            img = item.select_one('img')
            title = img['alt'] if img else item.get_text(strip=True)
            url = normalize_url(base_domain, item.get('href')) 
            if title and url:
                headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'TVBS'})
        except Exception as e:
            logging.warning(f"🟡 TVBS Level 3 剖析錯誤: {e}")
    for item in soup.select('div.hero_sub a.sub_item'):
        try:
            title = item.select_one('h3').get_text(strip=True)
            url = normalize_url(base_domain, item.get('href'))
            if title and url and 'news.tvbs.com.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'TVBS'})
        except Exception as e:
            logging.warning(f"🟡 TVBS Level 2 剖析錯誤: {e}")
    for item in soup.select('div.section_news a.news_popular'):
        try:
            title = item.select_one('h2').get_text(strip=True)
            url = normalize_url(base_domain, item.get('href'))
            if title and url and 'news.tvbs.com.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'TVBS'})
        except Exception as e:
            logging.warning(f"🟡 TVBS Level 1 剖析錯誤: {e}")
    logging.info(f"💡 TVBS 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_ebc_headlines():
    """(5/9) 抓取東森新聞 (EBC) 頭條"""
    logging.info("--- (5/9) 正在抓取 EBC 東森新聞頭條 ---")
    base_url = 'https://news.ebc.net.tw'
    soup = get_soup(base_url)
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div.latest_news a.swiper-slide'):
        try:
            title_element = item.select_one('h3.slide_title')
            title = item.get('data-title') or (title_element.get_text(strip=True) if title_element else None)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'ebc.net.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'EBC'})
        except Exception as e:
            logging.warning(f"🟡 EBC Level 3 剖析錯誤: {e}")
    for item in soup.select('div.hot_news div.list_slider li a'):
        try:
            title = item.select_one('h3.item_title').get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'ebc.net.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'EBC'})
        except Exception as e:
            logging.warning(f"🟡 EBC Level 2 剖析錯誤: {e}")
    for item in soup.select('div.focus_box div.section_content a.item'):
        try:
            title = item.select_one('h3.item_title').get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'ebc.net.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'EBC'})
        except Exception as e:
            logging.warning(f"🟡 EBC Level 1 剖析錯誤: {e}")
    logging.info(f"💡 EBC 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_nownews_headlines():
    """(6/9) 抓取 NOWnews 今日新聞頭條"""
    logging.info("--- (6/9) 正在抓取 NOWnews 今日新聞頭條 ---")
    base_url = 'https://www.nownews.com'
    soup = get_soup(base_url)
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div#focusSlider div.slider-item a'):
        try:
            title_element = item.select_one('figcaption')
            if not title_element:
                img_alt = item.select_one('img')
                title = img_alt['alt'] if img_alt else None
            else:
                title = title_element.get_text(strip=True)
                
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'nownews.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'NOWNEWS'})
        except Exception as e:
            logging.warning(f"🟡 NOWnews Level 3 剖析錯誤: {e}")
    for item in soup.select('ul.hotnews-wrap li a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'nownews.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'NOWNEWS'})
        except Exception as e:
            logging.warning(f"🟡 NOWnews Level 2 剖析錯誤: {e}")
    for item in soup.select('div.nnBlk.focus li.item a'):
        try:
            title = item.select_one('h3.title').get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'nownews.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'NOWNEWS'})
        except Exception as e:
            logging.warning(f"🟡 NOWnews Level 1 剖析錯誤: {e}")
    logging.info(f"💡 NOWnews 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_chinatimes_headlines():
    """(7/9) 抓取中時新聞網 (China Times) 頭條 (修正版：混合首頁與即時頁)"""
    logging.info("--- (7/9) 正在抓取 China Times 中時新聞網頭條 ---")
    base_url = 'https://www.chinatimes.com'
    headlines = []
    scraped_at = get_current_utc_time()

    # 首先，嘗試抓取首頁
    soup_homepage = get_soup(base_url)
    if soup_homepage:
        # Level 3: 焦點大圖 (focus-gallery)
        for item in soup_homepage.select('div.focus-gallery ul.item-group li.item-entry a'):
            try:
                title_element = item.select_one('h3.caption-title')
                title = title_element.get_text(separator=' ', strip=True) if title_element else None
                url = normalize_url(base_url, item.get('href'))
                if title and url and ('chinatimes.com' in url or 'ctwant.com' in url):
                    headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
            except Exception as e:
                logging.warning(f"🟡 China Times Level 3 剖析錯誤: {e}")

        # Level 2: 熱門新聞 (hot-news)
        for item in soup_homepage.select('section.hot-news ul.vertical-list li h4.title a'):
            try:
                title = item.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'chinatimes.com' in url:
                    headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
            except Exception as e:
                logging.warning(f"🟡 China Times Level 2 剖析錯誤: {e}")
    else:
        logging.warning("🟡 China Times 首頁抓取失敗，僅嘗試抓取即時頁面。")

    # 接著，抓取即時頁面 (使用您 .ipynb 中的邏輯)
    soup_realtime = get_soup(base_url + '/realtimenews/')
    if soup_realtime:
        # Level 1: 即時新聞 (realtimenews 頁面)
        for item in soup_realtime.select('div.article-list h3.title a'):
            try:
                title = item.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'chinatimes.com' in url:
                    headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
            except Exception as e:
                logging.warning(f"🟡 China Times Level 1 (realtimenews) 剖析錯誤: {e}")
    else:
         logging.warning("🟡 China Times 即時頁面抓取失敗。")
            
    logging.info(f"💡 China Times 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_ettoday_headlines():
    """(8/9) 抓取 ETtoday 新聞雲頭條 (來自您的 .ipynb)"""
    logging.info("--- (8/9) 正在抓取 ETtoday 新聞雲頭條 ---")
    base_url = 'https://www.ettoday.net'
    soup = get_soup(base_url + '/news/list.htm') 
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div.c1 > h3 > a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'ettoday.net' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'ETTODAY'})
        except Exception as e:
            logging.warning(f"🟡 ETtoday Level 3 剖析錯誤: {e}")
    for item in soup.select('div.part_list_2 > div > h3 > a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'ettoday.net' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'ETTODAY'})
        except Exception as e:
            logging.warning(f"🟡 ETtoday Level 1 剖析錯誤: {e}")
    logging.info(f"💡 ETtoday 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_ltn_headlines():
    """(9/9) 抓取自由時報 (LTN) 頭條 (來自您的 .ipynb)"""
    logging.info("--- (9/9) 正在抓取 LTN 自由時報頭條 ---")
    base_url = 'https://www.ltn.com.tw'
    soup = get_soup('https://news.ltn.com.tw/list/breakingnews') 
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div.focus-news ul.list li a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'ltn.com.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'LTN'})
        except Exception as e:
            logging.warning(f"🟡 LTN Level 3 剖析錯誤: {e}")
    for item in soup.select('ul.list li a.title'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'ltn.com.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'LTN'})
        except Exception as e:
            logging.warning(f"🟡 LTN Level 1 剖析錯誤: {e}")
    logging.info(f"💡 LTN 抓取到 {len(headlines)} 筆頭條")
    return headlines

# ===============================================================
# Cell 5: Part 1 - 主執行函式 (抓取頭條並儲存)
# ===============================================================

def run_part1_headline_fetch():
    """執行所有頭條抓取，並儲存到暫存 JSON 檔案"""
    logging.info("--- Part 1 開始：抓取所有 9 個網站頭條 ---")
    
    all_headlines = []
    all_headlines.extend(fetch_cna_headlines())
    all_headlines.extend(fetch_udn_headlines())
    all_headlines.extend(fetch_setn_headlines())
    all_headlines.extend(fetch_tvbs_headlines())
    all_headlines.extend(fetch_ebc_headlines())
    all_headlines.extend(fetch_nownews_headlines())
    all_headlines.extend(fetch_chinatimes_headlines())
    all_headlines.extend(fetch_ettoday_headlines())
    all_headlines.extend(fetch_ltn_headlines())
    
    logging.info(f"\n--- 總共抓取到 {len(all_headlines)} 筆頭條 (含重複) ---")
    
    unique_headlines = remove_duplicates(all_headlines)
    
    logging.info(f"--- 移除重複後，剩餘 {len(unique_headlines)} 筆獨立頭條 ---")

    try:
        with open(TEMP_JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(unique_headlines, f, ensure_ascii=False, indent=4)
        logging.info(f"✅ Part 1 完成：已將頭條暫存於 {TEMP_JSON_FILENAME}")
    except IOError as e:
        logging.error(f"🔥 Part 1 錯誤：無法寫入 JSON 檔案: {e}")
    except Exception as e:
        logging.error(f"🔥 Part 1 發生未知錯誤: {e}")

# ===============================================================
# Cell 6: Part 2 - 抓取各網站「文章內文」 (函式定義)
# ===============================================================

def scrape_cna_article(url):
    """CNA 文章頁面爬蟲"""
    content, time = scrape_article_content_base(
        url,
        content_selector='div.article-body',
        time_selector='div.update-time'
    )
    return clean_content(content), time

def scrape_udn_article(url):
    """UDN 文章頁面爬蟲"""
    content, time = scrape_article_content_base(
        url,
        content_selector='section.article-content__editor',
        time_selector='div.article-content__time'
    )
    return clean_content(content), time

def scrape_setn_article(url):
    """SETN 文章頁面爬蟲"""
    content, time = scrape_article_content_base(
        url,
        content_selector='div#Content1',
        time_selector='time.page-date'
    )
    return clean_content(content), time

def scrape_tvbs_article(url):
    """TVBS 文章頁面爬蟲"""
    content, time = scrape_article_content_base(
        url,
        content_selector='div.article_content',
        time_selector='div.time'
    )
    return clean_content(content), time

def scrape_ebc_article(url):
    """EBC 文章頁面爬蟲"""
    content, time = scrape_article_content_base(
        url,
        content_selector='div.article-main-content',
        time_selector='span.date'
    )
    return clean_content(content), time

def scrape_nownews_article(url):
    """NOWnews 文章頁面爬蟲"""
    soup = get_soup(url)
    if not soup:
        return 'N/A', get_current_utc_time()

    content_element = soup.select_one('div.article-content')
    content = 'N/A'
    if content_element:
        for figure in content_element.select('figure'):
            figure.decompose()
        for tool in content_element.select('div.media-tool'):
            tool.decompose()
        content = content_element.get_text(separator='\n', strip=True)

    time = safe_find_text(soup, 'time.date', default=get_current_utc_time())
    match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2})', time)
    if match:
        time = match.group(1).replace('/', '-')
    else:
        time = get_current_utc_time()
        
    return clean_content(content), time

def scrape_chinatimes_article(url):
    """China Times 文章頁面爬蟲"""
    content, time = scrape_article_content_base(
        url,
        content_selector='div.article-body',
        time_selector='div.meta-info time'
    )
    return clean_content(content), time

def scrape_ettoday_article(url):
    """ETtoday 文章頁面爬蟲 (來自您的 .ipynb 邏輯)"""
    content, time = scrape_article_content_base(
        url,
        content_selector='div.story',
        time_selector='time.date'
    )
    return clean_content(content), time 

def scrape_ltn_article(url):
    """LTN 文章頁面爬蟲 (來自您的 .ipynb 邏輯)"""
    content, time = scrape_article_content_base(
        url,
        content_selector='div[itemprop="articleBody"]',
        time_selector='span.time'
    )
    return clean_content(content), time

def scrape_article(url, source):
    """爬蟲路由器：根據來源 (source) 呼叫對應的爬蟲函式"""
    try:
        if source == 'CNA':
            return scrape_cna_article(url)
        elif source == 'UDN':
            return scrape_udn_article(url)
        elif source == 'SETN':
            return scrape_setn_article(url)
        elif source == 'TVBS':
            if 'news.tvbs.com.tw' in url:
                return scrape_tvbs_article(url)
            else:
                logging.warning(f"🟡 TVBS 網址非新聞站 ({url})，跳過。")
                return 'N/A', get_current_utc_time()
        elif source == 'EBC':
            return scrape_ebc_article(url)
        elif source == 'NOWNEWS':
            return scrape_nownews_article(url)
        elif source == 'CHINATIMES':
            return scrape_chinatimes_article(url)
        elif source == 'ETTODAY':
            return scrape_ettoday_article(url)
        elif source == 'LTN':
            return scrape_ltn_article(url)
        else:
            logging.warning(f"🟡 未知的來源: {source}，無法抓取 {url}")
            return 'N/A', get_current_utc_time()
    except Exception as e:
        logging.error(f"🔥 處理 {url} 時發生嚴重錯誤: {e}")
        return 'N/A', get_current_utc_time()

# ===============================================================
# Cell 7: Part 2 - 主執行函式 (抓取新文章並附加到 DB)
# ===============================================================

def run_part2_scrape_and_append():
    """
    讀取 JSON，抓取所有頭條的內文，並將這批新的快照
    **附加(Append)** 到現有的 7 欄位 CSV 資料庫 (News_dataset.csv)。
    """
    logging.info(f"\n--- Part 2 開始：抓取文章內文並附加到 {DB_FILENAME} ---")
    
    # 1. 檢查主資料庫是否存在，這將決定我們是否需要寫入 Header
    file_exists = os.path.exists(DB_FILENAME)
    if file_exists:
        logging.info(f"💡 偵測到現有資料庫 {DB_FILENAME}。新資料將會附加在檔案結尾。")
    else:
        logging.info(f"💡 找不到資料庫 {DB_FILENAME}。將會建立新檔案並寫入欄位名稱。")

    # 2. 讀取 Part 1 抓到的頭條 JSON
    try:
        with open(TEMP_JSON_FILENAME, 'r', encoding='utf-8') as f:
            headlines_to_scrape = json.load(f)
        logging.info(f"💡 已從 {TEMP_JSON_FILENAME} 載入 {len(headlines_to_scrape)} 筆頭條準備抓取。")
    except FileNotFoundError:
        logging.error(f"🔥 Part 2 錯誤：找不到 {TEMP_JSON_FILENAME}。請先執行 Part 1。")
        return
    except json.JSONDecodeError:
        logging.error(f"🔥 Part 2 錯誤：{TEMP_JSON_FILENAME} 檔案格式錯誤。")
        return

    if not headlines_to_scrape:
        logging.warning("👍 Part 2 完成：沒有從 Part 1 接收到任何頭條，無新資料寫入。")
        return

    logging.info(f"--- 開始抓取 {len(headlines_to_scrape)} 筆文章內文 ---")
    
    # 3. 抓取所有文章 (這就是一個完整的「快照」)
    new_snapshot_data = []
    count = 0
    for headline in headlines_to_scrape:
        count += 1
        url = headline['url']
        source = headline['source']
        logging.info(f"  ({count}/{len(headlines_to_scrape)}) 正在抓取 [{source}] {url}...")
        
        try:
            content, pub_time = scrape_article(url, source)
            
            if content != 'N/A' and content.strip(): 
                # 準備 7 個欄位的資料
                new_snapshot_data.append({
                    'url': url,
                    'title': headline['title'],
                    'content': content,
                    'source': source,
                    'published_at': pub_time,
                    'scraped_at': headline['scraped_at'],
                    'headline_level': headline['headline_level']
                })
                time.sleep(0.2) # 休息 0.2 秒
            else:
                logging.warning(f"  🟡 抓取失敗或內容為空，跳過: {url}")
        except Exception as e:
            logging.error(f"  🔥 抓取時發生嚴重錯誤 {url}: {e}")

    # 4. 整合並「附加」到 CSV
    if new_snapshot_data:
        try:
            # 1. 建立 7 欄位的 DataFrame
            # *** 修正：這裡使用 COLUMNS (7欄) ***
            new_df = pd.DataFrame(new_snapshot_data, columns=COLUMNS)
            
            # 2. **已移除** `credibility_label` 相關的所有程式碼
            
            # 3. 確保欄位型別正確 (Int64 支援 NaN)
            new_df['headline_level'] = pd.to_numeric(new_df['headline_level'], errors='coerce').astype('Int64')
            
            # 4. *** 關鍵邏輯：附加 (append) 模式 ***
            new_df.to_csv(
                DB_FILENAME, 
                mode='a',                 # 'a' 代表 append (附加)
                header=not file_exists,   # 只有在檔案不存在時才寫入 header
                index=False, 
                encoding='utf-8-sig'
            )
            
            logging.info(f"✅ Part 2 完成：成功抓取並「附加」 {len(new_snapshot_data)} 筆新快照到 {DB_FILENAME}")
            logging.info(f"您的舊資料已完整保留。")
            
        except IOError as e:
            logging.error(f"🔥 Part 2 錯誤：儲存到 {DB_FILENAME} 失敗: {e}")
        except Exception as e:
            logging.error(f"🔥 Part 2 儲存時發生未知錯誤: {e}")
    else:
        logging.warning("👍 Part 2 完成：本次快照未成功抓取到任何新文章。")

# ===============================================================
# Cell 8: 完整執行所有爬蟲任務
# ===============================================================

def main_execution():
    """
    依序執行所有爬蟲步驟
    """
    
    start_time = time.time()
    logging.info(f"======= 爬蟲任務開始於 {get_current_utc_time()} =======")
    
    # 步驟一：抓取所有頭條
    run_part1_headline_fetch()
    
    # 步驟二：抓取新文章內文並附加到您的 News_dataset.csv
    run_part2_scrape_and_append()
    
    end_time = time.time()
    sources = "CNA, UDN, SETN, TVBS, EBC, NOWnews, ChinaTimes, ETtoday, LTN"
    logging.info(f"\n======= 爬蟲任務完成 ({sources})，總耗時: {end_time - start_time:.2f} 秒 =======")

# 確保這個 .py 檔案被直接執行時，才會觸發 main_execution()
if __name__ == "__main__":
    
    # 步驟零：安裝套件
    setup_environment()
    
    # 立即執行主程式
    main_execution()

