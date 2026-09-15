"""
wuzzuf_collector.py

Fetches Wuzzuf's official public "all jobs" RSS feed and normalizes each
listing into a plain dict ready for insertion into the platform's `jobs` table.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

FEED_URL = "https://wuzzuf.net/feeds/all-jobs.xml"

def fetch_raw_feed():
    # هيدرز متكاملة ومتطورة لمتصفح حقيقي لتخطي حظر Cloudflare و 403 Forbidden
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    }
    
    try:
        response = requests.get(FEED_URL, headers=headers, timeout=15)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"[Warning] Wuzzuf fetch failed: {e}. Returning empty feed gracefully.")
        return None

def collect():
    raw = fetch_raw_feed()
    if not raw:
        return []
        
    jobs = []
    try:
        soup = BeautifulSoup(raw, "xml")
        items = soup.find_all("item")
        
        for item in items:
            title = item.find("title").text if item.find("title") else "N/A"
            link = item.find("link").text if item.find("link") else "N/A"
            description = item.find("description").text if item.find("description") else "N/A"
            pub_date = item.find("pubDate").text if item.find("pubDate") else "N/A"
            
            jobs.append({
                "title": title,
                "link": link,
                "description": description,
                "date": pub_date,
                "source": "wuzzuf"
            })
    except Exception as e:
        print(f"[Error] Parsing Wuzzuf feed failed: {e}")
        
    return jobs