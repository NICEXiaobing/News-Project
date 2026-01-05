#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ===============================================================
#   T-Forecast 全自動爬蟲系統 (V4.1 層級補完版)
#   更新日期: 2025-11-19
#   
#   [本次更新 V4.1]
#   1. 找回 L2 (主要/熱門新聞):
#      - Yahoo: 首頁第 6 篇後降為 L2。
#      - TVBS: 新增 /hot 熱門榜 -> L2。
#      - ETtoday: 新增 /hot-news.htm 熱門榜 -> L2。
#      - SETN: 新增 熱門新聞頁 -> L2。
#   2. 目標: 建立 L1(即時) -> L2(熱門) -> L3(焦點) 的完整金字塔數據。
# ===============================================================

import sys
import logging
import os
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
import time
import random
from difflib import SequenceMatcher
import warnings

# 忽略 SSL 警告
warnings.filterwarnings("ignore")

# ===============================================================
# 1. 環境與路徑設定
# ===============================================================
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

# 維持使用 V4 檔案，確保資料一致性
CONTENT_DB = os.path.join(BASE_DIR, 'news_data_v4_content.csv')
GOOGLE_DB  = os.path.join(BASE_DIR, 'news_data_v4_google.csv')
FINAL_DB   = os.path.join(BASE_DIR, 'news_data_v4_final.csv')

TEMP_JSON_FILENAME = os.path.join(BASE_DIR, 'temp_headlines_v4.json')
LOG_FILENAME = os.path.join(BASE_DIR, 'scraper_v4.log')

# --- Logging ---
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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
}

COLUMNS_CONTENT = ['url', 'title', 'content', 'source', 'published_at', 'scraped_at', 'headline_level']
COLUMNS_GOOGLE = ['category', 'url', 'title', 'source', 'published_at', 'scraped_at', 'headline_level']

JUNK_PATTERNS = re.compile(r'延伸閱讀|相關新聞|看更多|點我下載|▲|▼|（圖／.*(提供|翻攝)）|★.*?Disclaimer.*?★|下載APP|※.*?提醒您.*?※|記者.*?／.*?報導|編輯.*?／.*?報導')

# ===============================================================
# 2. 工具函式
# ===============================================================
def get_soup(url, is_xml=False):
    try:
        time.sleep(random.uniform(0.5, 1.5))
        response = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        parser = 'xml' if is_xml else 'lxml'
        return BeautifulSoup(response.text, parser)
    except Exception as e:
        logging.warning(f"🟡 抓取 {url} 失敗: {e}")
        return None

def normalize_url(base_url, link):
    if not link: return None
    link = link.strip()
    if link.startswith('//'): return 'https:' + link
    if link.startswith('/'): return base_url.rstrip('/') + link
    if link.startswith('http'): return link
    return base_url.rstrip('/') + '/' + link.lstrip('/')

def safe_find_text(soup, selector, default='N/A'):
    if not soup: return default
    if ',' in selector:
        selectors = [s.strip() for s in selector.split(',')]
        for sel in selectors:
            element = soup.select_one(sel)
            if element: return element.get_text(separator='\n', strip=True)
    else:
        element = soup.select_one(selector)
        if element: return element.get_text(separator='\n', strip=True)
    return default

def get_current_utc_time():
    taiwan_tz = timezone(timedelta(hours=8))
    return datetime.now(taiwan_tz).strftime("%Y-%m-%d %H:%M:%S")

def remove_duplicates(headlines):
    if not headlines: return []
    df = pd.DataFrame(headlines)
    # 排序：Level 3 > 2 > 1，確保同一篇新聞如果同時出現在熱門榜和即時榜，會被記為較高的等級
    df = df.sort_values('headline_level', ascending=False)
    df_unique = df.drop_duplicates(subset=['url'], keep='first')
    return df_unique.to_dict('records')

def clean_content(text):
    if text == 'N/A' or not text: return 'N/A'
    lines = text.split('\n')
    cleaned = [line.strip() for line in lines if not JUNK_PATTERNS.search(line) and len(line.strip()) > 10]
    return '\n'.join(cleaned).strip()

def scrape_article_content_base(url, content_selector_list, time_selector):
    soup = get_soup(url)
    if not soup: return 'N/A', get_current_utc_time()
    content = 'N/A'
    if isinstance(content_selector_list, list):
        for selector in content_selector_list:
            text = safe_find_text(soup, selector)
            if text != 'N/A' and len(text) > 20:
                content = text
                break
    else:
        content = safe_find_text(soup, content_selector_list)
    published_at = safe_find_text(soup, time_selector, default=get_current_utc_time())
    return content, published_at

def clean_google_link(link):
    if link.startswith("./"): return "https://news.google.com" + link[1:]
    return link

def similar(a, b):
    if not a or not b: return 0.0
    return SequenceMatcher(None, str(a), str(b)).ratio()

# ===============================================================
# 3. [Part 1] 頭條抓取 (V4.1 層級優化版)
# ===============================================================

def fetch_yahoo_headlines():
    """Yahoo: 首頁分層策略 (Top 5=L3, Rest=L2) + 即時 (L1)"""
    base_url = 'https://tw.news.yahoo.com'
    headlines = []
    scraped_at = get_current_utc_time()
    
    # 1. 首頁 (L3 & L2)
    soup_home = get_soup(base_url)
    if soup_home:
        for i, h3 in enumerate(soup_home.find_all('h3')):
            link_tag = h3.find('a', href=True)
            if link_tag:
                link = link_tag['href']
                title = link_tag.get_text(strip=True)
                if title and len(title) > 5 and ('/html' in link or '/news/' in link):
                    # ★ 新策略：前 5 篇為 L3，其餘為 L2 (填補 L2 空缺)
                    level = 3 if i < 5 else 2
                    headlines.append({'url': normalize_url(base_url, link), 'title': title, 'headline_level': level, 'scraped_at': scraped_at, 'source': 'YAHOO'})

    # 2. 即時列表 (L1)
    soup_real = get_soup(base_url + '/archive')
    if soup_real:
        for h3 in soup_real.find_all('h3'):
            link_tag = h3.find('a', href=True)
            if link_tag:
                link = link_tag['href']
                title = link_tag.get_text(strip=True)
                if title and len(title) > 5:
                    headlines.append({'url': normalize_url(base_url, link), 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'YAHOO'})
    return headlines

def fetch_tvbs_headlines():
    """TVBS: 即時 (L1) + 熱門 (L2)"""
    base_domain = 'https://news.tvbs.com.tw'
    headlines = []
    scraped_at = get_current_utc_time()
    
    # 1. 即時列表 (L1)
    soup_real = get_soup(base_domain + '/realtime')
    if soup_real:
        for item in soup_real.select('.news_list .list li a'):
            title = item.select_one('h2')
            if title:
                headlines.append({'url': normalize_url(base_domain, item.get('href')), 'title': title.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'TVBS'})
                
    # 2. 熱門列表 (L2) - ★ 新增
    soup_hot = get_soup(base_domain + '/hot')
    if soup_hot:
        for item in soup_hot.select('.news_list .list li a'):
            title = item.select_one('h2')
            if title:
                headlines.append({'url': normalize_url(base_domain, item.get('href')), 'title': title.get_text(strip=True), 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'TVBS'})
    return headlines

def fetch_ettoday_headlines():
    """ETtoday: 即時 (L1) + 熱門 (L2)"""
    base_url = 'https://www.ettoday.net'
    headlines = []
    scraped_at = get_current_utc_time()
    
    # 1. 即時 (L1)
    soup = get_soup(base_url + '/news/news-list.htm')
    if soup:
        for item in soup.select('.part_list_2 h3 a'):
            title = item.get_text(strip=True)
            if title and len(title) > 5:
                headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'ETTODAY'})
    
    # 2. 熱門 (L2) - ★ 新增
    soup_hot = get_soup(base_url + '/news/hot-news.htm')
    if soup_hot:
        for item in soup_hot.select('.part_list_2 h3 a'):
            title = item.get_text(strip=True)
            if title and len(title) > 5:
                headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'ETTODAY'})
    return headlines

def fetch_setn_headlines():
    """SETN: 即時 (L1) + 熱門 (L2) + 焦點 (L3)"""
    base_url = 'https://www.setn.com'
    soup = get_soup(base_url)
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    
    # L3: 首頁焦點
    for item in soup.select('div.focus_news div.captionText a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'SETN'})
    
    # L1: 首頁即時區
    for item in soup.select('div.immediate-news-area div.news-list li a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'SETN'})
        
    # L2: 熱門新聞頁 - ★ 新增
    soup_hot = get_soup(base_url + '/ViewAll.aspx?PageGroupID=6')
    if soup_hot:
        for item in soup_hot.select('.news-list-group h3 a'):
            headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'SETN'})
            
    return headlines

# --- 其他維持穩定 ---

def fetch_ltn_headlines():
    headlines = []
    scraped_at = get_current_utc_time()
    base_url = 'https://news.ltn.com.tw'
    soup = get_soup('https://news.ltn.com.tw/list/breakingnews')
    if soup:
        for item in soup.select('div.whitecon ul.list li a'):
            title = item.get('title')
            if not title:
                h3 = item.select_one('h3.title')
                if h3: title = h3.get_text(strip=True)
            link = item.get('href')
            if title and link:
                headlines.append({'url': normalize_url(base_url, link), 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'LTN'})
    if len(headlines) == 0:
        soup_home = get_soup('https://news.ltn.com.tw/')
        if soup_home:
            for item in soup_home.select('a.tit'):
                title = item.get_text(strip=True)
                link = item.get('href')
                if title and link and 'news.ltn' in link:
                    headlines.append({'url': normalize_url(base_url, link), 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'LTN'})
    return headlines

def fetch_cna_headlines():
    base_url = 'https://www.cna.com.tw'
    soup = get_soup(base_url + '/list/aall.aspx')
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('#jsMainList li a'):
        title_div = item.select_one('div.listText h2')
        title = title_div.get_text(strip=True) if title_div else item.get_text(strip=True)
        link = item.get('href')
        if title and link:
            headlines.append({'url': normalize_url(base_url, link), 'title': title, 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'CNA'})
    return headlines

def fetch_chinatimes_headlines():
    base_url = 'https://www.chinatimes.com'
    headlines = []
    scraped_at = get_current_utc_time()
    soup_real = get_soup(base_url + '/realtimenews/')
    if soup_real:
        for item in soup_real.select('h3.title a'):
            headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
    soup_home = get_soup(base_url)
    if soup_home:
        for item in soup_home.select('.main-news .title a'):
             headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
    return headlines

def fetch_ebc_headlines():
    base_url = 'https://news.ebc.net.tw'
    soup = get_soup(base_url)
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.find_all('a', href=True):
        link = item['href']
        if '/news/' in link:
            title = item.get('title') or item.get_text(strip=True)
            if title and len(title) > 8:
                headlines.append({'url': normalize_url(base_url, link), 'title': title, 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'EBC'})
    unique = {h['url']: h for h in headlines}.values()
    return list(unique)

def fetch_udn_headlines():
    base_url = 'https://udn.com'
    soup = get_soup(base_url + '/news/breaknews/1')
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div.story-list__text h2 a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'UDN'})
    return headlines

def fetch_nownews_headlines():
    base_url = 'https://www.nownews.com'
    headlines = []
    scraped_at = get_current_utc_time()
    soup_home = get_soup(base_url)
    if soup_home:
        for item in soup_home.select('div#focusSlider div.slider-item a'):
            title = item.select_one('figcaption').get_text(strip=True) if item.select_one('figcaption') else "N/A"
            headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'NOWNEWS'})
    soup_real = get_soup(base_url + '/news/realtime')
    if soup_real:
        for item in soup_real.select('h3.title a'):
            headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'NOWNEWS'})
    return headlines

def run_part1_headline_fetch():
    logging.info("--- [V4.1] Part 1: 抓取 9 大媒體頭條 ---")
    all_headlines = []
    fetchers = [
        (fetch_yahoo_headlines, "YAHOO"),
        (fetch_cna_headlines, "CNA"),
        (fetch_udn_headlines, "UDN"),
        (fetch_setn_headlines, "SETN"),
        (fetch_tvbs_headlines, "TVBS"),
        (fetch_nownews_headlines, "NOWnews"),
        (fetch_ettoday_headlines, "ETtoday"),
        (fetch_ltn_headlines, "LTN"),
        (fetch_ebc_headlines, "EBC")
    ]
    for fetcher, name in fetchers:
        try:
            data = fetcher()
            logging.info(f"   {name}: {len(data)} 筆")
            all_headlines.extend(data)
            time.sleep(1)
        except Exception as e: logging.error(f"   🔥 {name} 失敗: {e}")
    unique_headlines = remove_duplicates(all_headlines)
    try:
        with open(TEMP_JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(unique_headlines, f, ensure_ascii=False, indent=4)
        logging.info(f"✅ Part 1 完成: 總計 {len(unique_headlines)} 筆")
    except Exception as e: logging.error(f"🔥 Part 1 存檔失敗: {e}")

# ===============================================================
# 4. [Part 2] 內文抓取
# ===============================================================
def scrape_yahoo_article(url):
    content, time = scrape_article_content_base(url, ['div.caas-body', 'article'], 'div.caas-attr-time-style')
    return clean_content(content), time
def scrape_cna_article(url):
    content, time = scrape_article_content_base(url, ['div.paragraph', 'div.article-body', 'div.centralContent'], 'div.update-time')
    return clean_content(content), time
def scrape_udn_article(url):
    content, time = scrape_article_content_base(url, 'section.article-content__editor', 'div.article-content__time')
    return clean_content(content), time
def scrape_setn_article(url):
    content, time = scrape_article_content_base(url, 'div#Content1', 'time.page-date')
    return clean_content(content), time
def scrape_tvbs_article(url):
    content, time = scrape_article_content_base(url, 'div.article_content', 'div.time')
    return clean_content(content), time
def scrape_ebc_article(url):
    content, time = scrape_article_content_base(url, ['div.fncnews-content', 'div.article-main-content', 'div.raw-style'], 'span.date')
    return clean_content(content), time
def scrape_nownews_article(url):
    soup = get_soup(url)
    if not soup: return 'N/A', get_current_utc_time()
    content_element = soup.select_one('div.article-content')
    content = content_element.get_text(separator='\n', strip=True) if content_element else 'N/A'
    time = safe_find_text(soup, 'time.date', default=get_current_utc_time())
    return clean_content(content), time
def scrape_chinatimes_article(url):
    content, time = scrape_article_content_base(url, ['div.article-body', 'article', 'div.article-content'], 'div.meta-info time')
    return clean_content(content), time
def scrape_ettoday_article(url):
    content, time = scrape_article_content_base(url, 'div.story', 'time.date')
    return clean_content(content), time
def scrape_ltn_article(url):
    content, time = scrape_article_content_base(url, ['div.text', 'div[itemprop="articleBody"]', 'div.whitecon'], 'span.time')
    return clean_content(content), time

def scrape_article(url, source):
    try:
        if source == 'YAHOO': return scrape_yahoo_article(url)
        elif source == 'CNA': return scrape_cna_article(url)
        elif source == 'UDN': return scrape_udn_article(url)
        elif source == 'SETN': return scrape_setn_article(url)
        elif source == 'TVBS': return scrape_tvbs_article(url) if 'news.tvbs.com.tw' in url else ('N/A', get_current_utc_time())
        elif source == 'NOWNEWS': return scrape_nownews_article(url)
        elif source == 'ETTODAY': return scrape_ettoday_article(url)
        elif source == 'LTN': return scrape_ltn_article(url)
        elif source == 'EBC': return scrape_ebc_article(url)
        elif source == 'CHINATIMES': return scrape_chinatimes_article(url)
        else: return 'N/A', get_current_utc_time()
    except: return 'N/A', get_current_utc_time()

def run_part2_scrape_and_append():
    logging.info("--- [V4.1] Part 2: 抓取內文並存檔 ---")
    try:
        with open(TEMP_JSON_FILENAME, 'r', encoding='utf-8') as f:
            headlines = json.load(f)
    except: return

    new_data = []
    for h in headlines:
        try:
            if not h.get('url'): continue
            content, pub_time = scrape_article(h['url'], h['source'])
            if content != 'N/A' and len(content) > 50:
                new_data.append({
                    'url': h['url'], 'title': h['title'], 'content': content, 'source': h['source'],
                    'published_at': pub_time, 'scraped_at': h['scraped_at'], 'headline_level': h['headline_level']
                })
                time.sleep(0.1)
        except: pass
        
    if new_data:
        df = pd.DataFrame(new_data, columns=COLUMNS_CONTENT)
        is_exist = os.path.exists(CONTENT_DB)
        df.to_csv(CONTENT_DB, mode='a', header=not is_exist, index=False, encoding='utf-8-sig')
        logging.info(f"✅ Part 2 完成: 寫入 {len(new_data)} 筆 到 {CONTENT_DB}")
    else:
        logging.warning("⚠️ Part 2 警告: 未抓到任何有效內文")

# ===============================================================
# 5. [Part 3] Google News 極速爬蟲
# ===============================================================
GOOGLE_URLS = {
    "Google_精選": "https://news.google.com/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRFZxYUdjU0JYcG9MVlJYR2dKVVZ5Z0FQAQ?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
    "焦點頭條": "https://news.google.com/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRFZxYUdjU0JXVnVMVWRDR2dKSlRpZ0FQAQ?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
    "國際財經": "https://news.google.com/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx6TVdZU0JXVnVMVWRDR2dKSlRpZ0FQAQ?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
    "科技科學": "https://news.google.com/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRGRqTVhZU0JXVnVMVWRDR2dKSlRpZ0FQAQ?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
    "運動體育": "https://news.google.com/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRFp1ZEdvU0JXVnVMVWRDR2dKSlRpZ0FQAQ?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant"
}
def run_part3_google_v3():
    logging.info("--- [V4.1] Part 3: Google News 標籤抓取 ---")
    data_list = []
    for cat, url in GOOGLE_URLS.items():
        try:
            time.sleep(random.uniform(2, 4))
            res = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            articles = soup.find_all('article')
            
            for i, art in enumerate(articles):
                all_links = art.find_all('a', href=True)
                candidate_links = []
                for l in all_links:
                    if './read/' in l['href'] or './articles/' in l['href']:
                        txt = l.get_text(strip=True)
                        aria = l.get('aria-label') or ""
                        if not txt and not aria:
                            parent = l.find_parent(['h3', 'h4'])
                            if parent: txt = parent.get_text(strip=True)
                        final_text = txt if len(txt) > len(aria) else aria
                        candidate_links.append({'link': l, 'len': len(final_text), 'text': final_text})
                if not candidate_links: continue
                candidate_links.sort(key=lambda x: x['len'], reverse=True)
                best_link = candidate_links[0]
                title = best_link['text']
                if not title: title = "無標題"
                full_url = clean_google_link(best_link['link']['href'])
                src_div = art.find('div', class_='vr1PYe')
                source = src_div.get_text(strip=True) if src_div else "Google"
                hl = 3 if ((cat == "焦點頭條" or cat == "Google_精選") and i < 5) else 2
                data_list.append({'category': cat, 'url': full_url, 'title': title, 'source': source, 'published_at': get_current_utc_time(), 'scraped_at': get_current_utc_time(), 'headline_level': hl})
        except Exception as e: logging.error(f"Google [{cat}] 失敗: {e}")

    if data_list:
        df = pd.DataFrame(data_list, columns=COLUMNS_GOOGLE)
        is_exist = os.path.exists(GOOGLE_DB)
        df.to_csv(GOOGLE_DB, mode='a', header=not is_exist, index=False, encoding='utf-8-sig')
        logging.info(f"✅ Part 3 完成: 寫入 {len(data_list)} 筆")

# ===============================================================
# 6. [Part 4] 合併
# ===============================================================
def run_part4_merge_v3():
    logging.info("--- [V4.1] Part 4: 資料合併 ---")
    if not os.path.exists(CONTENT_DB) or not os.path.exists(GOOGLE_DB): return
    try:
        df_content = pd.read_csv(CONTENT_DB)
        df_google = pd.read_csv(GOOGLE_DB)
        if 'google_level' not in df_content.columns: df_content['google_level'] = 0
        if 'is_google_top' not in df_content.columns: df_content['is_google_top'] = False
        
        recent_google = df_google.tail(1000).to_dict('records')
        match_count = 0
        for i, row in df_content.iterrows():
            if row['google_level'] > 0: continue
            best_score = 0
            best_level = 0
            v_title = str(row['title'])
            if len(v_title) < 4: continue
            for g in recent_google:
                g_title = str(g['title'])
                if len(g_title) < 4: continue
                if str(row['source']) in str(g['source']) or str(g['source']) in str(row['source']):
                    score = similar(v_title, g_title)
                    if score > best_score:
                        best_score = score
                        best_level = g['headline_level']
            if best_score > 0.5:
                df_content.at[i, 'google_level'] = best_level
                df_content.at[i, 'is_google_top'] = True
                match_count += 1
        df_content.to_csv(FINAL_DB, index=False, encoding='utf-8-sig')
        logging.info(f"🎉 合併完成! 新增 {match_count} 筆關聯")
    except Exception as e: logging.error(f"合併失敗: {e}")

# ===============================================================
# 7. 執行
# ===============================================================
def main_execution():
    start_time = time.time()
    logging.info(f"======= V4.1 任務開始 {get_current_utc_time()} =======")
    requests.packages.urllib3.disable_warnings()
    run_part1_headline_fetch()
    run_part2_scrape_and_append()
    run_part3_google_v3()
    run_part4_merge_v3()
    end_time = time.time()
    logging.info(f"======= V4.1 任務結束，耗時 {end_time - start_time:.2f} 秒 =======")

if __name__ == "__main__":
    main_execution()