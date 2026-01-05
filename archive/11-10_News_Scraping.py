#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ===============================================================
#
#   九合一新聞爬蟲 (CNA, UDN, SETN, TVBS, EBC, NOWnews, ETtoday, LTN, ChinaTimes)
#   版本: v26 (2025-11-11 - 全動態抓取穩定版)
#
#   - 根據使用者建議，為求最高穩定性，將 "全部 9 個網站" 的
#     第一層列表抓取 (Part 1) 均改為 `get_soup_dynamic` (Selenium 可見式瀏覽器)。
#   - 這是最穩定，但執行速度最慢的版本。
#
#   - (1) get_soup_dynamic 等待時間延長至 5 秒。
#   - (2) 修正 UDN, SETN, TVBS 的動態 CSS 選擇器。
#   - (3) Part 2 (內文頁): 保持使用 get_soup_static (requests) 以確保速度。
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
import hashlib 

# *** v21-v26 導入：Selenium + Chrome ***
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    logging.error("🔥 錯誤：未找到 'selenium' 或 'webdriver-manager' 套件。")
    logging.error("請在終端機執行: /opt/anaconda3/bin/python3 -m pip install selenium webdriver-manager")
    sys.exit(1)

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

DB_FILENAME = os.path.join(BASE_DIR, 'news_dataset.csv')
LOG_FILENAME = os.path.join(BASE_DIR, 'news_scraper.log') 

# --- 設定日誌 (Logging) ---
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
    
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILENAME, 'a', 'utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- 全域變數 ---
try:
    ua = UserAgent()
except Exception as e:
    logging.warning(f"🟡 Fake-UserAgent 初始化失敗 ({e})，將使用備用 UA。")
    class UA_Fallback:
        @property
        def random(self):
            return 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ua = UA_Fallback()

SNAPSHOT_COLUMNS = [
    'url', 'title', 'headline_level', 'snapshot_at', 'full_content', 'source', 'url_hash'
]

# ===============================================================
# Cell 2: 通用工具函式 (Helper Functions)
# ===============================================================

def get_current_utc_time():
    """回傳當前的 ISO 8601 格式 UTC 時間字串"""
    return datetime.now(timezone.utc).isoformat()

def normalize_url(base_url, relative_url):
    """將相對 URL 轉換為絕對 URL"""
    if not relative_url:
        return None
    if relative_url.startswith(('http://', 'https://')):
        return relative_url
    if relative_url.startswith('//'):
        return 'https:' + relative_url
    return requests.compat.urljoin(base_url, relative_url)


def get_soup_static(url, encoding=None):
    """
    (靜態抓取 - 用於 Part 2 內文) 
    發送 HTTP GET 請求並回傳 BeautifulSoup 解析後的物件。
    """
    try:
        headers = {'User-Agent': ua.random}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        if encoding:
            response.encoding = encoding
        else:
            response.encoding = response.apparent_encoding
            
        soup = BeautifulSoup(response.text, 'lxml')
        return soup
    except requests.exceptions.Timeout:
        logging.warning(f"🟡 [Static] 請求超時: {url}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            logging.error(f"🔥 [Static] 請求被拒絕 (403 Forbidden): {url}.")
        else:
            logging.warning(f"🟡 [Static] HTTP 錯誤 {e.response.status_code}: {url}")
    except requests.exceptions.RequestException as e:
        logging.warning(f"🟡 [Static] 請求失敗: {url} ({e})")
    except Exception as e:
        logging.error(f"🔥 [Static] 解析 BeautifulSoup 失敗: {url} ({e})")
        
    return None

def get_soup_dynamic(url, wait_time=5): # *** v25 變更：預設等待時間延長至 5 秒 ***
    """
    (動態抓取 - 用於 Part 1 列表) 
    *** v22 變更：使用「可見」的 Chrome 瀏覽器來繞過 Bot 偵測。***
    """
    driver = None
    try:
        chrome_options = ChromeOptions()
        # *** v22 關鍵修改：移除 '--headless' ***
        # chrome_options.add_argument("--headless") 
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"user-agent={ua.random}")
        
        # 隱藏「Chrome 正受到自動測試軟體控制」的提示
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 讓 Selenium 看起來更不像機器人
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        logging.info("   (一個「可見」的 Chrome 視窗即將打開...)")
        driver.get(url)
        
        logging.info(f"   (Chrome 正在等待 {wait_time} 秒讓 JavaScript 載入...)")
        time.sleep(wait_time)
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'lxml')
        return soup
        
    except Exception as e:
        logging.error(f"🔥 [Dynamic] Selenium (Chrome) 執行失敗: {url} ({e})")
        return None
    finally:
        if driver:
            driver.quit() # 確保瀏覽器被關閉

# ===============================================================
# Cell 3: (v15 中已停用 JSON 快取功能)
# ===============================================================
# (此 Cell 保持空白)

# ===============================================================
# Cell 4: 九大媒體爬蟲函式 (v26 版 - 全動態抓取 + 最終選擇器)
# ===============================================================

# 
# (1/9) CNA 中央社 (*** v26 動態抓取 ***)
#
def fetch_cna_headlines():
    """(1/9) 抓取 CNA 中央社 頭條"""
    logging.info("--- (1/9) 正在抓取 CNA 中央社頭條 ---")
    base_url = 'https://www.cna.com.tw'
    list_url = 'https://www.cna.com.tw/list/aall.aspx'
    headlines = []
    scraped_at = get_current_utc_time()
    
    soup = get_soup_dynamic(list_url, wait_time=5) 
    
    if not soup:
        logging.warning("🟡 CNA 抓取失敗。")
        return headlines
    try:
        headline_level = 1
        for item in soup.select('div#js-real-time-list li a'): # v25 確認 OK
            try:
                title = item.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                
                if title and url and 'cna.com.tw' in url:
                    headlines.append({
                        'url': url, 
                        'title': title, 
                        'headline_level': headline_level, 
                        'scraped_at': scraped_at, 
                        'source': 'CNA'
                    })
                    headline_level += 1
            except Exception as e:
                logging.warning(f"🟡 CNA 剖析列表項目錯誤: {e}")
    except Exception as e:
        logging.error(f"🔥 CNA 爬蟲執行時發生未預期錯誤: {e}")
    logging.info(f"💡 CNA 抓取到 {len(headlines)} 筆頭條")
    return headlines

#
# (2/9) UDN 聯合新聞網 (*** v26 動態抓取 ***)
#
def fetch_udn_headlines():
    """(2/9) 抓取 UDN 聯合新聞網 頭條"""
    logging.info("--- (2/9) 正在抓取 UDN 聯合新聞網頭條 ---")
    list_url = 'https://udn.com/news/breaknews/1'
    base_url = 'https://udn.com'
    headlines = []
    scraped_at = get_current_utc_time()
    
    soup = get_soup_dynamic(list_url, wait_time=5)
    
    if not soup:
        logging.warning("🟡 UDN 抓取失敗。")
        return headlines
    try:
        headline_level = 1
        for item in soup.select('div.story-list__news div.story-list__text h2 a'): # v25 修正
            try:
                title = item.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'udn.com' in url and '/event/' not in url:
                    headlines.append({
                        'url': url, 
                        'title': title, 
                        'headline_level': headline_level, 
                        'scraped_at': scraped_at, 
                        'source': 'UDN'
                    })
                    headline_level += 1
            except Exception as e:
                logging.warning(f"🟡 UDN 剖析列表項目錯誤: {e}")
    except Exception as e:
        logging.error(f"🔥 UDN 爬蟲執行時發生未預期錯誤: {e}")
    logging.info(f"💡 UDN 抓取到 {len(headlines)} 筆頭條")
    return headlines

#
# (3/9) SETN 三立新聞網 (*** v26 動態抓取 ***)
#
def fetch_setn_headlines():
    """(3/9) 抓取 SETN 三立新聞網 頭條"""
    logging.info("--- (3/9) 正在抓取 SETN 三立新聞網頭條 ---")
    list_url = 'https://www.setn.com/ViewAll.aspx'
    base_url = 'https://www.setn.com'
    headlines = []
    scraped_at = get_current_utc_time()
    
    soup = get_soup_dynamic(list_url, wait_time=5) 
    
    if not soup:
        logging.warning("🟡 SETN 抓取失敗。")
        return headlines
    try:
        headline_level = 1
        # (v25) 修正為動態 HTML 的正確選擇器
        for item in soup.select('div.NewsList div.newsItems h3.view-li-title a.gt'): 
            try:
                title = item.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url:
                    headlines.append({
                        'url': url, 
                        'title': title, 
                        'headline_level': headline_level, 
                        'scraped_at': scraped_at, 
                        'source': 'SETN'
                    })
                    headline_level += 1
            except Exception as e:
                logging.warning(f"🟡 SETN 剖析列表項目錯誤: {e}")
    except Exception as e:
        logging.error(f"🔥 SETN 爬蟲執行時發生未預期錯誤: {e}")
    logging.info(f"💡 SETN 抓取到 {len(headlines)} 筆頭條")
    return headlines

#
# (4/9) TVBS 新聞網 (*** v26 動態抓取 ***)
#
def fetch_tvbs_headlines():
    """(4/9) 抓取 TVBS 新聞網 頭條"""
    logging.info("--- (4/9) 正在抓取 TVBS 新聞網頭條 ---")
    list_url = 'https://news.tvbs.com.tw/realtime'
    base_url = 'https://news.tvbs.com.tw'
    headlines = []
    scraped_at = get_current_utc_time()
    
    soup = get_soup_dynamic(list_url, wait_time=5)
    
    if not soup:
        logging.warning("🟡 TVBS 抓取失敗。")
        return headlines
    try:
        headline_level = 1
        # (v25) 修正為動態 HTML 的正確選擇器
        for item in soup.select('div.news_list div.list ul li a'): 
            try:
                # (v25) 修正標題邏輯
                title_tag = item.find('h2', class_='txt')
                title = title_tag.get_text(strip=True) if title_tag else None
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'tvbs.com.tw' in url:
                    headlines.append({
                        'url': url, 
                        'title': title, 
                        'headline_level': headline_level, 
                        'scraped_at': scraped_at, 
                        'source': 'TVBS'
                    })
                    headline_level += 1
            except Exception as e:
                logging.warning(f"🟡 TVBS 剖析列表項目錯誤: {e}")
    except Exception as e:
        logging.error(f"🔥 TVBS 爬蟲執行時發生未預期錯誤: {e}")
    logging.info(f"💡 TVBS 抓取到 {len(headlines)} 筆頭條")
    return headlines

#
# (5/9) EBC 東森新聞 (*** v26 動態抓取 ***)
#
def fetch_ebc_headlines():
    """(5/9) 抓取 EBC 東森新聞 頭條"""
    logging.info("--- (5/9) 正在抓取 EBC 東森新聞頭條 ---")
    base_url = 'https://news.ebc.net.tw'
    list_url = 'https://news.ebc.net.tw/'
    headlines = []
    scraped_at = get_current_utc_time()
    
    soup = get_soup_dynamic(list_url, wait_time=5)
    
    if not soup:
        logging.warning("🟡 EBC 抓取失敗。")
        return headlines
    try:
        headline_level = 1
        for item in soup.select('div.hot_news .list_slider .swiper-slide-active li a.item.row_box'): # v25 確認 OK
            try:
                title = item.find('h3', class_='item_title').get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'ebc.net.tw' in url:
                    headlines.append({
                        'url': url, 
                        'title': title, 
                        'headline_level': headline_level, 
                        'scraped_at': scraped_at, 
                        'source': 'EBC'
                    })
                    headline_level += 1
            except Exception as e:
                logging.warning(f"🟡 EBC 剖析列表項目錯誤: {e}")
    except Exception as e:
        logging.error(f"🔥 EBC 爬蟲執行時發生未預期錯誤: {e}")
    logging.info(f"💡 EBC 抓取到 {len(headlines)} 筆頭條")
    return headlines

#
# (6/9) NOWnews 今日新聞 (*** v26 動態抓取 ***)
#
def fetch_nownews_headlines():
    """(6/9) 抓取 NOWnews 今日新聞 頭條"""
    logging.info("--- (6/9) 正在抓取 NOWnews 今日新聞頭條 ---")
    base_url = 'https://www.nownews.com'
    list_url = 'https://www.nownews.com/'
    headlines = []
    scraped_at = get_current_utc_time()
    
    # (v26) 統一改用動態抓取
    soup = get_soup_dynamic(list_url, wait_time=5) 
    
    if not soup:
        logging.warning("🟡 NOWnews 抓取失敗。")
        return headlines
    try:
        headline_level = 1
        for item in soup.select('div.nnBlk.tabs div.tabItem.active ul li a'): # v25 確認 OK
            try:
                title = item.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'nownews.com' in url:
                    headlines.append({
                        'url': url, 
                        'title': title, 
                        'headline_level': headline_level, 
                        'scraped_at': scraped_at, 
                        'source': 'NOWnews'
                    })
                    headline_level += 1
            except Exception as e:
                logging.warning(f"🟡 NOWnews 剖析列表項目錯誤: {e}")
    except Exception as e:
        logging.error(f"🔥 NOWnews 爬蟲執行時發生未預期錯誤: {e}")
    logging.info(f"💡 NOWnews 抓取到 {len(headlines)} 筆頭條")
    return headlines

#
# (7/9) ETtoday 新聞雲 (*** v26 動態抓取 ***)
#
def fetch_ettoday_headlines():
    """(7/9) 抓取 ETtoday 新聞雲 頭條"""
    logging.info("--- (7/9) 正在抓取 ETtoday 新聞雲頭條 ---")
    base_url = 'https://www.ettoday.net'
    list_url = 'https://www.ettoday.net/'
    headlines = []
    scraped_at = get_current_utc_time()
    
    soup = get_soup_dynamic(list_url, wait_time=5)
    
    if not soup:
        logging.warning("🟡 ETtoday 抓取失敗。")
        return headlines
    try:
        headline_level = 1
        for item in soup.select('div.part_list_8 div.piece h2.title a'): # v25 確認 OK
            try:
                title = item.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'ettoday.net' in url and '/events/' not in url:
                    headlines.append({
                        'url': url, 
                        'title': title, 
                        'headline_level': headline_level, 
                        'scraped_at': scraped_at, 
                        'source': 'ETtoday'
                    })
                    headline_level += 1
            except Exception as e:
                logging.warning(f"🟡 ETtoday 剖析列表項目錯誤: {e}")
    except Exception as e:
        logging.error(f"🔥 ETtoday 爬蟲執行時發生未預期錯誤: {e}")
    logging.info(f"💡 ETtoday 抓取到 {len(headlines)} 筆頭條")
    return headlines

#
# (8/9) ChinaTimes 中時新聞網 (*** v26 動態抓取 ***)
#
def fetch_chinatimes_headlines():
    """(8/9) 抓取 ChinaTimes 中時新聞網 頭條"""
    logging.info("--- (8/9) 正在抓取 China Times 中時新聞網頭條 ---")
    base_url = 'https://www.chinatimes.com'
    
    # (v26) 統一改用動態抓取
    soup = get_soup_dynamic(base_url, wait_time=5) 
    
    if not soup:
        logging.warning("🟡 China Times 首頁抓取失敗。")
        return []
    headlines = []
    scraped_at = get_current_utc_time()
    try:
        # L3
        headline_level_3 = 1
        for item in soup.select('div.focus-gallery div.adaptive-gallery li.item-entry h3.caption-title a'):
            try:
                title = item.get_text(separator=' ', strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and ('chinatimes.com' in url or 'ctwant.com' in url):
                    headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
                    headline_level_3 += 1
            except Exception as e:
                logging.warning(f"🟡 China Times Level 3 剖析錯誤: {e}")
        # L2
        headline_level_2 = 1
        for item in soup.select('section.focus-news ul.vertical-list li h3.title a'):
            try:
                title = item.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'chinatimes.com' in url:
                    headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
                    headline_level_2 += 1
            except Exception as e:
                logging.warning(f"🟡 China Times Level 2 剖析錯誤: {e}")
        # L1
        headline_level_1 = 1
        for item in soup.select('div#news-pane-1-1 ul.vertical-list li h4.title a'):
            try:
                title = item.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'chinatimes.com' in url:
                    headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
                    headline_level_1 += 1
            except Exception as e:
                logging.warning(f"🟡 China Times Level 1 剖析錯誤: {e}")
    except Exception as e:
        logging.error(f"🔥 ChinaTimes 爬蟲執行時發生未預期錯誤: {e}")
    logging.info(f"💡 China Times 抓取到 {len(headlines)} 筆頭條")
    return headlines

#
# (9/9) LTN 自由時報 (*** v26 動態抓取 ***)
#
def fetch_ltn_headlines():
    """(9/9) 抓取自由時報 (LTN) 頭條"""
    logging.info("--- (9/9) 正在抓取 LTN 自由時報頭條 ---")
    base_url = 'https://news.ltn.com.tw'
    headlines = []
    scraped_at = get_current_utc_time()
    try:
        # (v26) 統一改用動態抓取
        soup = get_soup_dynamic('https://www.ltn.com.tw/', wait_time=5) 
        
        if not soup:
            logging.warning("🟡 LTN 首頁抓取失敗。")
            return []
        # L3
        headline_level_3 = 1
        for item in soup.select('div#ltn_focus a.swiper-slide'):
            try:
                title = item.get('title')
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'ltn.com.tw' in url and not 'pv6.ltn.com.tw' in url:
                    headlines.append({'url': url, 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'LTN'})
                    headline_level_3 += 1
            except Exception as e:
                logging.warning(f"🟡 LTN Level 3 剖析錯誤: {e}")
        # L2
        headline_level_2 = 1
        for item in soup.select('div.news10 ul.content_list li a'):
            try:
                title = item.get('title')
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'ltn.com.tw' in url and not 'pv6.ltn.com.tw' in url:
                    headlines.append({'url': url, 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'LTN'})
                    headline_level_2 += 1
            except Exception as e:
                logging.warning(f"🟡 LTN Level 2 剖析錯誤: {e}")
        # L1
        headline_level_1 = 1
        for item in soup.select('div.breakingnews[data-desc="即時清單"] ul.content_list li a'):
            try:
                title = item.get('title')
                if not title:
                    h3_tag = item.find('h3')
                    if h3_tag:
                        title = h3_tag.get_text(strip=True)
                url = normalize_url(base_url, item.get('href'))
                if title and url and 'ltn.com.tw' in url and not 'pv6.ltn.com.tw' in url:
                    headlines.append({'url': url, 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'LTN'})
                    headline_level_1 += 1
            except Exception as e:
                logging.warning(f"🟡 LTN Level 1 剖析錯誤: {e}")
    except Exception as e:
        logging.error(f"🔥 LTN 爬蟲執行時發生未預期錯誤: {e}")
    logging.info(f"💡 LTN 抓取到 {len(headlines)} 筆頭條")
    return headlines


# ===============================================================
# Cell 5: Part 1 執行函式 (v26 全動態模式)
# ===============================================================

def run_part1_headline_fetch():
    """
    執行 Part 1：抓取所有媒體的頭條。
    v26 版：全部使用動態抓取
    """
    logging.info("--- Part 1 開始：抓取所有媒體頭條 (v26 全動態模式) ---")
    
    all_headlines = [] 

    fetch_functions = [
        fetch_cna_headlines,        # 動態 (Selenium - 可見)
        fetch_udn_headlines,        # 動態 (Selenium - 可見)
        fetch_setn_headlines,       # 動態 (Selenium - 可見)
        fetch_tvbs_headlines,       # 動態 (Selenium - 可見)
        fetch_ebc_headlines,        # 動態 (Selenium - 可見)
        fetch_nownews_headlines,    # 動態 (Selenium - 可見)
        fetch_ettoday_headlines,    # 動態 (Selenium - 可見)
        fetch_ltn_headlines,        # 動態 (Selenium - 可見)
        fetch_chinatimes_headlines  # 動態 (Selenium - 可見)
    ]

    for func in fetch_functions:
        try:
            headlines = func() 
            all_headlines.extend(headlines)
            logging.info(f"✓ {func.__name__} 完成，抓取到 {len(headlines)} 筆頭條。")
        except Exception as e:
            logging.error(f"🔥 執行 {func.__name__} 時發生嚴重錯誤: {e}")
            
        sleep_time = random.uniform(2, 5)
        logging.info(f"   (隨機延遲 {sleep_time:.2f} 秒，模擬真人瀏覽...)")
        time.sleep(sleep_time)

    logging.info("--- Part 1 完成 ---")
    logging.info(f"總共抓取 {len(all_headlines)} 筆頭條 (L1+L2+L3)，準備寫入快照。")
    
    return all_headlines

# ===============================================================
# Cell 6: Part 2 核心功能 (抓取內文並建立快照) (v26 版)
# ===============================================================

def get_article_content(url, source):
    """
    根據不同媒體來源，抓取文章內文。
    (v26) 內文抓取全部使用靜態的 get_soup_static
    """
    
    soup = get_soup_static(url) # 使用靜態 requests 抓取內文
    
    if not soup:
        return f"錯誤：抓取失敗 {url}"

    content = ""
    selectors = []

    try:
        # (v16 的內文選擇器)
        if source == 'CNA':
            selectors = ['div.article-content p', 'div.central-text p']
        elif source == 'UDN':
            selectors = ['section.article-content__editor p']
        elif source == 'SETN':
            selectors = ['div#Content1 p']
        elif source == 'TVBS':
            selectors = ['div.article_content p', 'div.article_content div']
        elif source == 'EBC':
            selectors = ['div.raw-style p']
        elif source == 'NOWnews':
            selectors = ['article.article-content p']
        elif source == 'ETtoday':
            selectors = ['div.story p']
        elif source == 'LTN':
            selectors = ['div.text p']
        elif source == 'CHINATIMES':
            if 'ctwant.com' in url:
                selectors = ['div.article-body p']
            else:
                selectors = ['div.article-body p']
        
        elements = soup.select(', '.join(selectors))
        
        if not elements:
            elements = soup.find_all('p')
            if not elements:
                 return f"錯誤：找不到任何 <p> 標籤 {url}"
                 
        for el in elements:
            text = el.get_text(strip=True)
            if text and '延伸閱讀' not in text and '記者' not in text[:5] and '▲' not in text[:5] and '圖／' not in text[:5]:
                content += text + "\n"
        
        return content if content else f"錯誤：內容為空 {url}"

    except Exception as e:
        logging.warning(f"🟡 剖析內文失敗: {url} ({e})")
        return f"錯誤：剖析失敗 {url} ({e})"

def create_snapshot_data(all_headlines_list):
    """
    接收 Part 1 產出的「所有頭條列表」，逐一抓取內文，
    並轉換為準備寫入 CSV 的 DataFrame。
    """
    snapshot_data = [] 
    
    if not all_headlines_list:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)

    total = len(all_headlines_list)
    logging.info(f"--- Part 2 開始：準備抓取 {total} 筆文章內文 (包含重複內文以建立快照) ---")
    
    content_cache = {}

    for i, headline in enumerate(all_headlines_list):
        url = headline['url']
        source = headline['source']
        
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        content = ""

        if url in content_cache:
            content = content_cache[url]
            logging.info(f"  ({i+1}/{total}) [快取] 正在處理 [{source}] {url}...")
        else:
            logging.info(f"  ({i+1}/{total}) [抓取] 大家好，我是 {source}，正在抓取 {url}...")
            
            time.sleep(random.uniform(0.5, 1.5))
            
            content = get_article_content(url, source)
            content_cache[url] = content

        snapshot_entry = {
            'url': url,
            'title': headline['title'],
            'headline_level': headline['headline_level'],
            'snapshot_at': headline['scraped_at'],
            'full_content': content,
            'source': source,
            'url_hash': url_hash
        }
        snapshot_data.append(snapshot_entry)

    logging.info(f"✓ Part 2 內文抓取與處理完成。")
    
    df = pd.DataFrame(snapshot_data, columns=SNAPSHOT_COLUMNS)
    return df

# ===============================================================
# Cell 7: Part 2 執行函式 (v15 完整快照版)
# ===============================================================

def run_part2_scrape_and_append():
    """
    執行 Part 2：
    1. 執行 Part 1 取得「所有」可見頭條
    2. 抓取這些頭條的內文
    3. 將這些「完整快照」附加 (Append) 到 `news_dataset.csv`
    """
    
    # 1. 執行 Part 1
    all_headlines_list = run_part1_headline_fetch()
    
    if not all_headlines_list:
        logging.info("👍 Part 2 完成：Part 1 未抓取到任何頭條。")
        return

    # 2. 抓取文章內文
    snapshot_df = create_snapshot_data(all_headlines_list)
    snapshot_data = snapshot_df.to_dict('records')

    # 3. 附加 (Append) 到 CSV
    if snapshot_data:
        try:
            file_exists = os.path.exists(DB_FILENAME)
            
            if not file_exists:
                logging.warning(f"🟡 {DB_FILENAME} 不存在。將自動建立新檔案並寫入 7 欄位標頭。")
            
            snapshot_df.to_csv(
                DB_FILENAME, 
                mode='a',
                header=not file_exists,
                index=False, 
                encoding='utf-8-sig'
            )
            
            logging.info(f"✅ Part 2 完成：成功抓取並「附加」 {len(snapshot_data)} 筆快照到 {DB_FILENAME}")
            
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
    
    run_part2_scrape_and_append()
    
    end_time = time.time()
    sources = "CNA, UDN, SETN, TVBS, EBC, NOWnews, ETtoday, LTN, ChinaTimes"
    logging.info(f"\n======= 爬蟲任務完成 ({sources})，總耗時: {end_time - start_time:.2f} 秒 =======\n\n")

# 確保這個 .py 檔案被直接執行時，才會觸發 main_execution()
if __name__ == "__main__":
    main_execution()