#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ===============================================================
#
#   九合一新聞爬蟲 (RSS 優先混合版)
#   版本: v32 (2025-11-11 - RSS 最終穩定版)
#
#   - 徹底移除 Playwright，專注於 Requests + RSS 穩定性。
#   - 【修復 CNA, CT RSS 404】: 更新為最新可用的 RSS/Requests 網址。
#   - 【修復 EBC 內文】: 內文爬蟲邏輯最終修正，避免 Part 2 抓取失敗。
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
import random 

# v22: 導入 warnings 模組以忽略 SSL 警告
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
# v22: 關閉 SSL 驗證警告
warnings.simplefilter('ignore', InsecureRequestWarning)

try:
    from fake_useragent import UserAgent
except ImportError:
    logging.error("🔥 錯誤：未找到 'fake-useragent' 套件。")
    logging.error("請在終端機執行: /opt/anaconda3/bin/python3 -m pip install fake-useragent")
    sys.exit(1)

# --- 設定路徑 ---
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd() 

# v17: 依使用者要求，更新檔案名稱
DB_FILENAME = os.path.join(BASE_DIR, 'News_dataset.csv')
TEMP_JSON_FILENAME = os.path.join(BASE_DIR, 'News_dataset_cache.json')
LOG_FILENAME = os.path.join(BASE_DIR, 'News_dataset.log') 

# --- 設定日誌 ---
logger = logging.getLogger()
logger.setLevel(logging.INFO) 
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')

if logger.hasHandlers():
    logger.handlers.clear()

file_handler = logging.FileHandler(LOG_FILENAME, encoding='utf-8', mode='a') 
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# --- 全域變數 ---
try:
    ua = UserAgent()
except Exception as e:
    logging.warning(f"🟡 UserAgent 初始化失敗: {e}. 將使用備用 User-Agent。")
    ua = None

# v11: 您喜歡的 7 欄位結構
COLUMNS = [
    'url', 
    'title', 
    'content', 
    'source',
    'published_at', 
    'scraped_at', 
    'headline_level'
]

# v29: 修正 v28 的 SyntaxError
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
# Cell 2: 環境設定 (v32 僅檢查 requests 相關套件)
# ===============================================================
def setup_environment():
    """
    檢查並安裝 requests 相關的 Python 套件。
    """
    packages = [
        ('requests', 'requests'),
        ('beautifulsoup4', 'bs4'),
        ('pandas', 'pandas'),
        ('lxml', 'lxml'),
        ('fake-useragent', 'fake_useragent')
    ]
    logging.info("--- 正在檢查並安裝必要套件 ---")
    
    python_executable = "/opt/anaconda3/bin/python3" # 統一路徑
    
    for pkg_name, import_name in packages:
        try:
            importlib.import_module(import_name)
            logging.info(f"✅ {pkg_name} (導入名: {import_name}) 已正確導入。")
        except ImportError:
            logging.warning(f"--- 正在安裝 {pkg_name} ---")
            try:
                subprocess.check_call([python_executable, "-m", "pip", "install", pkg_name])
                logging.info(f"✅ {pkg_name} 安裝完成！")
            except Exception as e:
                logging.error(f"🔥 安裝 {pkg_name} 失敗: {e}")
                logging.error(f"請手動在您的終端機執行: {python_executable} -m pip install {pkg_name}")
                sys.exit(1)

    logging.info("\n🎉 所有必要的套件都已準備就緒！")

# ===============================================================
# Cell 3: 輔助函式 (v31 - 無 Playwright)
# ===============================================================
def get_dynamic_user_agent():
    """v16: 動態取得 User-Agent"""
    if ua:
        try:
            return ua.random
        except Exception: 
            return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
    else:
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'

def get_soup(url):
    """(Requests) 輔助函式：發送請求並取得 BeautifulSoup 物件 (v22 SSL 略過版)"""
    try:
        headers = {'User-Agent': get_dynamic_user_agent()}
        
        # v22: 設置 verify=False 來略過 SSL 憑證驗證
        response = requests.get(url, headers=headers, timeout=20, verify=False)
        
        response.raise_for_status() 
        return BeautifulSoup(response.text, 'lxml')
    except requests.RequestException as e:
        logging.warning(f"🟡 抓取 {url} 失敗 (Requests): {e}")
        return None

def get_soup_rss(url):
    """(RSS) 專門用於抓取 RSS Feed 的函式"""
    try:
        headers = {'User-Agent': 'RSS-Crawl/1.0'}
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        # RSS 內容是 XML 格式
        return BeautifulSoup(response.content, 'xml')
    except requests.RequestException as e:
        logging.warning(f"🟡 抓取 RSS {url} 失敗: {e}")
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

def get_current_utc_time(include_microseconds=False):
    """
    v18: 取得目前 UTC+8 (台灣時間) 的時間字串。
    預設回傳 'YYYY-MM-DD HH:MM:SS' 格式。
    """
    taiwan_tz = timezone(timedelta(hours=8))
    now = datetime.now(taiwan_tz)
    if include_microseconds:
        return now.strftime("%Y-%m-%d %H:%M:%S.%f")
    else:
        return now.strftime("%Y-%m-%d %H:%M:%S")

def remove_duplicates(headlines):
    """移除重複的頭條，保留 URL 唯一，並優先取等級 (level) 最高的"""
    if not headlines: 
        return []
    
    df = pd.DataFrame(headlines)
    df = df.sort_values('headline_level', ascending=False)
    df_unique = df.drop_duplicates(subset=['url'], keep='first')
    
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
        if len(line) < 10: 
            continue
        cleaned_lines.append(line)
    
    full_text = '\n'.join(cleaned_lines)
    return re.sub(r'\n{2,}', '\n', full_text).strip()

def format_published_time(time_str):
    """v19: 統一處理時間字串的函式"""
    time_str = str(time_str).strip()
    time_str = re.sub(r'^(發布時間|更新時間)：', '', time_str).strip()
    
    match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2})', time_str)
    if match:
        return match.group(1).replace('/', '-')

    match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2})', time_str)
    if match:
        return match.group(1).replace('/', '-') + ":00"

    match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', time_str)
    if match:
        return match.group(1).replace('/', '-') + " 00:00:00"

    return get_current_utc_time() # 備案

def scrape_article_content_base(url, content_selector, time_selector):
    """
    v19: 抓取文章內文的通用基礎函式 (使用 format_published_time)
    """
    time.sleep(random.uniform(0.5, 1.5))
    soup = get_soup(url) 
    
    if not soup:
        return 'N/A', get_current_utc_time()
    
    content = safe_find_text(soup, content_selector, default='N/A')
    published_at_raw = safe_find_text(soup, time_selector, default=get_current_utc_time()) 
    
    published_at = format_published_time(published_at_raw)
            
    return clean_content(content), published_at

# ===============================================================
# Cell 4: Part 1 - 抓取所有網站的頭條新聞 (v32 函式定義)
# ===============================================================

def fetch_cna_headlines():
    """(1/9) 抓取 CNA (v32 規則: RSS Feed - 修正 404)"""
    logging.info("--- (1/9) 正在抓取 CNA 中央社頭條 (v32 - RSS) ---")
    base_url = 'https://www.cna.com.tw'
    rss_url = 'https://www.cna.com.tw/cna2017/feed/rss/aall.xml' #
    
    soup = get_soup_rss(rss_url) 
    
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    
    # RSS 解析
    for item in soup.find_all('item'):
        try:
            title = item.find('title').get_text(strip=True)
            url = item.find('link').get_text(strip=True)
            
            if title and url and 'www.cna.com.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'CNA'})
        except Exception as e:
            logging.warning(f"🟡 CNA v32 RSS 剖析錯誤: {e}")
            
    logging.info(f"💡 CNA 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_udn_headlines():
    """(2/9) 抓取 UDN (v19 規則 - Requests)"""
    logging.info("--- (2/9) 正在抓取 UDN 聯合新聞網頭條 ---")
    time.sleep(random.uniform(1.5, 4.0))
    base_url = 'https://udn.com'
    soup = get_soup(base_url + '/news/breaknews/1') 
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    
    for item in soup.select('div.context-box__content--main h2 a, div.context-box__content--main h3 a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'udn.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'UDN'})
        except Exception as e:
            logging.warning(f"🟡 UDN L3 剖析錯誤: {e}")

    for item in soup.select('div.story-list__news div.story-list__text h2 a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'udn.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'UDN'})
        except Exception as e:
            logging.warning(f"🟡 UDN L1 剖析錯誤: {e}")
            
    logging.info(f"💡 UDN 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_setn_headlines():
    """(3/9) 抓取 SETN (v32 規則: Requests)"""
    # v32: SETN 無公共 RSS，回歸 Requests + 列表頁抓取
    logging.info("--- (3/9) 正在抓取 SETN 三立新聞網頭條 (v32 - Requests) ---")
    time.sleep(random.uniform(1.5, 4.0))
    base_url = 'https://www.setn.com'
    # 列表頁
    soup = get_soup(base_url + '/ViewAll.aspx')
    
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    
    # L2 (焦點新聞)
    for item in soup.select('div.col-lg-8.col-xs-12.pagelist-L div.news-g div.col-sm-12 a'):
        try:
            title = item.get('title')
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'setn.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'SETN'})
        except Exception as e:
            logging.warning(f"🟡 SETN v32 L2 剖析錯誤: {e}")
            
    # L1 (即時列表)
    for item in soup.select('div.row.NewsList div.col-sm-12 a'):
        try:
            title = item.get('title')
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'setn.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'SETN'})
        except Exception as e:
            logging.warning(f"🟡 SETN v32 L1 剖析錯誤: {e}")
            
    logging.info(f"💡 SETN 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_tvbs_headlines():
    """(4/9) 抓取 TVBS (v32 規則: RSS Feed)"""
    logging.info("--- (4/9) 正在抓取 TVBS 新聞網頭條 (v32 - RSS) ---")
    base_domain = 'https://news.tvbs.com.tw' 
    rss_url = 'https://news.tvbs.com.tw/web_api/play_feed_realtime' #

    soup = get_soup_rss(rss_url)
    
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    
    # RSS 解析
    for item in soup.find_all('item'):
        try:
            title = item.find('title').get_text(strip=True)
            url = item.find('link').get_text(strip=True)
            
            if title and url and 'news.tvbs.com.tw' in url:
                # TVBS RSS 無層級資訊，統一設為 L1
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'TVBS'})
        except Exception as e:
            logging.warning(f"🟡 TVBS v32 RSS 剖析錯誤: {e}")
            
    logging.info(f"💡 TVBS 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_ebc_headlines():
    """(5/9) 抓取 EBC (v19 規則 - Requests)"""
    logging.info("--- (5/9) 正在抓取 EBC 東森新聞頭條 ---")
    time.sleep(random.uniform(1.5, 4.0))
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
            logging.warning(f"🟡 EBC L3 剖析錯誤: {e}")
            
    for item in soup.select('div.hot_news div.list_slider li a'):
        try:
            title = item.select_one('h3.item_title').get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'ebc.net.tw' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'EBC'})
        except Exception as e:
            logging.warning(f"🟡 EBC L2 剖析錯誤: {e}")
            
    for item in soup.select('div.newest_news-list a.item, div.hot-news-wrap a.item'):
        try:
            title_element = item.select_one('h3.item_title, span.title')
            title = title_element.get_text(strip=True) if title_element else None
            url = normalize_url(base_url, item.get('href'))
            
            if title and url and 'ebc.net.tw' in url:
                level = 2 if 'star.ebc.net.tw' in url else 1
                headlines.append({'url': url, 'title': title, 'headline_level': level, 'scraped_at': scraped_at, 'source': 'EBC'})
        except Exception as e:
            logging.warning(f"🟡 EBC L1/L2 剖析錯誤: {e}")
            
    logging.info(f"💡 EBC 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_nownews_headlines():
    """(6/9) 抓取 NOWnews (v19 規則 - Requests)"""
    logging.info("--- (6/9) 正在抓取 NOWnews 今日新聞頭條 ---")
    time.sleep(random.uniform(1.5, 4.0))
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
            logging.warning(f"🟡 NOWnews L3 剖析錯誤: {e}")
            
    for item in soup.select('ul.hotnews-wrap li a'):
        try:
            title = item.get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'nownews.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'NOWNEWS'})
        except Exception as e:
            logging.warning(f"🟡 NOWnews L2 剖析錯誤: {e}")
            
    for item in soup.select('div.nnBlk.focus li.item a'):
        try:
            title = item.select_one('h3.title').get_text(strip=True)
            url = normalize_url(base_url, item.get('href'))
            if title and url and 'nownews.com' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'NOWNEWS'})
        except Exception as e:
            logging.warning(f"🟡 NOWnews L1 剖析錯誤: {e}")
            
    logging.info(f"💡 NOWnews 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_chinatimes_headlines():
    """(7/9) 抓取 ChinaTimes (v32 規則: Requests - 修正 404)"""
    logging.info("--- (7/9) 正在抓取 China Times 中時新聞網頭條 (v32 - Requests) ---")
    time.sleep(random.uniform(1.5, 4.0))
    base_url = 'https://www.chinatimes.com'
    headlines = []
    scraped_at = get_current_utc_time()

    # v32: 回歸 Requests 網頁 (即時新聞頁)，因為 RSS 404
    soup = get_soup(base_url + '/realtimenews/')
    
    if soup:
        # L1 (即時列表)
        for item in soup.select('div.article-list h3.title a'):
            try:
                title = item.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'chinatimes.com' in url:
                    headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
            except Exception as e:
                logging.warning(f"🟡 China Times v32 L1 剖析錯誤: {e}")
    else:
         logging.warning("🟡 China Times v32 即時頁面抓取失敗。")
            
    logging.info(f"💡 China Times 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_ettoday_headlines():
    """(8/9) 抓取 ETtoday (v32 規則: Requests - 修正網址)"""
    # v32: ETtoday 容易 0 筆，但 Requests 仍是目前最快的免費方案。
    logging.info("--- (8/9) 正在抓取 ETtoday 新聞雲頭條 (v32 - Requests) ---")
    time.sleep(random.uniform(1.5, 4.0))
    base_url = 'https://www.ettoday.net'
    
    # 修正網址錯誤
    soup = get_soup(base_url + '/news/news-list.htm') 
    
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    
    # L1 (即時列表)
    for item in soup.select('div.part_list_2 div.piece.clearfix'):
        try:
            title_el = item.select_one('h3 a')
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            url = normalize_url(base_url, title_el.get('href'))
            
            is_hot = item.select_one('i.icon_hot, i.icon_focus')
            level = 3 if is_hot else 1 # 有標記的升為 Level 3
            
            if title and url and 'ettoday.net' in url:
                headlines.append({'url': url, 'title': title, 'headline_level': level, 'scraped_at': scraped_at, 'source': 'ETTODAY'})
        except Exception as e:
            logging.warning(f"🟡 ETtoday v32 L1/L3 剖析錯誤: {e}")
            
    logging.info(f"💡 ETtoday 抓取到 {len(headlines)} 筆頭條")
    return headlines

def fetch_ltn_headlines():
    """(9/9) 抓取 LTN (v32 規則: RSS Feed)"""
    logging.info("--- (9/9) 正在抓取 LTN 自由時報頭條 (v32 - RSS) ---")
    base_url = 'https://www.ltn.com.tw'
    rss_url = 'https://news.ltn.com.tw/rss/all.xml' #
    
    soup = get_soup_rss(rss_url)
    
    if not soup:
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    
    # RSS 解析
    for item in soup.find_all('item'):
        try:
            title = item.find('title').get_text(strip=True)
            url = item.find('link').get_text(strip=True)
            
            if title and url and 'ltn.com.tw' in url:
                # LTN RSS 無層級資訊，統一設為 L1
                headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'LTN'})
        except Exception as e:
            logging.warning(f"🟡 LTN v32 RSS 剖析錯誤: {e}")
            
    logging.info(f"💡 LTN 抓取到 {len(headlines)} 筆頭條")
    return headlines

# ===============================================================
# Cell 5: Part 1 - 主執行函式 (v32 修正版)
# ===============================================================

def run_part1_headline_fetch():
    """執行所有頭條抓取，並儲存到暫存 JSON 檔案"""
    logging.info("--- Part 1 開始：抓取所有 9 個網站頭條 (v32 RSS 優先模式) ---")
    
    all_headlines = []
    
    # --- RSS 快速通道 (CNA, LTN, TVBS, CT) ---
    all_headlines.extend(fetch_cna_headlines())
    all_headlines.extend(fetch_ltn_headlines())
    all_headlines.extend(fetch_tvbs_headlines())
    all_headlines.extend(fetch_chinatimes_headlines())
    
    # --- Requests 備用通道 (UDN, SETN, EBC, NOWnews, ETtoday) ---
    all_headlines.extend(fetch_udn_headlines())
    all_headlines.extend(fetch_setn_headlines())
    all_headlines.extend(fetch_ebc_headlines())
    all_headlines.extend(fetch_nownews_headlines())
    all_headlines.extend(fetch_ettoday_headlines())
    
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
    
    return unique_headlines

# ===============================================================
# Cell 6: Part 2 - 抓取各網站「文章內文」 (v32 EBC 內文修復)
# ===============================================================

def scrape_cna_article(url):
    """CNA 文章頁面爬蟲"""
    return scrape_article_content_base(
        url,
        content_selector='div.article-body',
        time_selector='div.update-time'
    )

def scrape_udn_article(url):
    """UDN 文章頁面爬蟲"""
    return scrape_article_content_base(
        url,
        content_selector='section.article-content__editor',
        time_selector='div.article-content__time'
    )

def scrape_setn_article(url):
    """SETN 文章頁面爬蟲"""
    return scrape_article_content_base(
        url,
        content_selector='div#Content1',
        time_selector='time.page-date'
    )

def scrape_tvbs_article(url):
    """TVBS 文章頁面爬蟲"""
    return scrape_article_content_base(
        url,
        content_selector='div.article_content',
        time_selector='div.time'
    )

def scrape_ebc_article(url):
    """EBC 文章頁面爬蟲 (v32: 最終內文規則)"""
    time.sleep(random.uniform(0.5, 1.5))
    soup = get_soup(url) 
    if not soup:
        return 'N/A', get_current_utc_time()

    content = 'N/A'
    
    # v32: 採用最常出現的兩個選擇器作為主規則
    if 'star.ebc.net.tw' in url:
        # 這是「星光雲」的版型
        content = safe_find_text(soup, 'div.article-content', default='N/A')
    else:
        # 這是「東森新聞」的版型
        content = safe_find_text(soup, 'div[itemprop=\"articleBody\"]', default='N/A')

    # 內文找不到時，採用第二組備案 (v31 失敗後，作為 v32 的最終保險)
    if content == 'N/A' or not content:
         content = safe_find_text(soup, 'div.article-main-content', default='N/A') # news.ebc.net.tw 舊版備案
    if content == 'N/A' or not content:
         content = safe_find_text(soup, 'div.article-content-page', default='N/A') # star.ebc.net.tw 舊版備案

    # 抓取時間
    time_raw = safe_find_text(soup, 'span.date', default=get_current_utc_time())

    published_at = format_published_time(time_raw)
    return clean_content(content), published_at


def scrape_nownews_article(url):
    """NOWnews 文章頁面爬蟲"""
    time.sleep(random.uniform(0.5, 1.5))
    soup = get_soup(url) 
    if not soup:
        return 'N/A', get_current_utc_time()

    content_element = soup.select_one('div.article-content')
    content = 'N/A'
    if content_element:
        # 移除圖片和多媒體標籤
        for figure in content_element.select('figure'):
            figure.decompose()
        for tool in content_element.select('div.media-tool'):
            tool.decompose()
        content = content_element.get_text(separator='\n', strip=True)

    time_raw = safe_find_text(soup, 'time.date', default=get_current_utc_time())
    published_at = format_published_time(time_raw)
        
    return clean_content(content), published_at

def scrape_chinatimes_article(url):
    """China Times 文章頁面爬蟲"""
    return scrape_article_content_base(
        url,
        content_selector='div.article-body',
        time_selector='div.meta-info time'
    )

def scrape_ettoday_article(url):
    """ETtoday 文章頁面爬蟲"""
    return scrape_article_content_base(
        url,
        content_selector='div.story',
        time_selector='time.date'
    ) 

def scrape_ltn_article(url):
    """LTN 文章頁面爬蟲"""
    return scrape_article_content_base(
        url,
        content_selector='div[itemprop="articleBody"]',
        time_selector='span.time'
    )

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
# Cell 7: Part 2 - 主執行函式 (v32 已確認無須修改)
# ===============================================================

def run_part2_scrape_and_append(headlines_to_scrape):
    """
    抓取 Part 1 傳入的頭條內文，並將這批新的快照
    **附加(Append)** 到現有的 7 欄位 CSV 資料庫 (News_dataset.csv)。
    """
    logging.info(f"\n--- Part 2 開始：抓取文章內文並附加到 {DB_FILENAME} ---")
    
    file_exists = os.path.exists(DB_FILENAME)
    if file_exists:
        logging.info(f"💡 偵測到現有資料庫 {DB_FILENAME}。新資料將會附加在檔案結尾。")
    else:
        logging.info(f"💡 找不到資料庫 {DB_FILENAME}。將會建立新檔案並寫入欄位名稱。")

    if not headlines_to_scrape:
        logging.warning("👍 Part 2 完成：沒有從 Part 1 接收到任何頭條，無新資料寫入。")
        return

    logging.info(f"--- 開始抓取 {len(headlines_to_scrape)} 筆文章內文 ---")
    
    new_snapshot_data = []
    count = 0
    total = len(headlines_to_scrape)
    
    for headline in headlines_to_scrape:
        count += 1
        url = headline['url']
        source = headline['source']
        logging.info(f"  ({count}/{total}) 正在抓取 [{source}] {url}...")
        
        try:
            content, pub_time = scrape_article(url, source)
            
            if content and content != 'N/A': 
                new_snapshot_data.append({
                    'url': url,
                    'title': headline['title'],
                    'content': content,
                    'source': source,
                    'published_at': pub_time, 
                    'scraped_at': headline['scraped_at'], 
                    'headline_level': headline['headline_level']
                })
            else:
                logging.warning(f"  🟡 抓取失敗或內容為空，跳過: {url}")
        except Exception as e:
            logging.error(f"  🔥 抓取時發生嚴重錯誤 {url}: {e}")

    if new_snapshot_data:
        try:
            new_df = pd.DataFrame(new_snapshot_data, columns=COLUMNS)
            
            new_df['headline_level'] = pd.to_numeric(new_df['headline_level'], errors='coerce').astype('Int64')
            
            new_df.to_csv(
                DB_FILENAME,              
                mode='a',                 
                header=not file_exists,   
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
# Cell 8: 完整執行所有爬蟲任務 (v31 修正版)
# ===============================================================

def main_execution():
    """
    依序執行所有爬蟲步驟
    """
    
    start_time = time.time()
    logging.info(f"======= 爬蟲任務開始於 {get_current_utc_time()} =======")
    
    # 步驟一：抓取所有頭條
    headlines_list = run_part1_headline_fetch()
    
    # 步驟二：抓取新文章內文並附加到 News_dataset.csv
    run_part2_scrape_and_append(headlines_list)
    
    end_time = time.time()
    # v31: 啟用所有 9 站 (RSS/Requests 混合)
    sources = "CNA(RSS), UDN, SETN, TVBS(RSS), EBC, NOWnews, ChinaTimes(RSS), ETtoday, LTN(RSS)"
    logging.info(f"\n======= 爬蟲任務完成 ({sources})，總耗時: {end_time - start_time:.2f} 秒 =========")

# 確保這個 .py 檔案被直接執行時，才會觸發 main_execution()
if __name__ == "__main__":
    
    # 步驟零：自動檢查並安裝 requests 相關套件
    setup_environment()
    
    # 立即執行主程式
    main_execution()