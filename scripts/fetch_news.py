#!/usr/bin/env python3
"""Собирает заголовки теннисных новостей из открытых RSS-лент в news.json.

Только стандартная библиотека. Хранятся заголовок, ссылка, источник и время;
текст статей не копируется. Если ни одна лента не ответила, старый файл не трогаем.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

FEEDS = [
    ("Чемпионат", "https://www.championat.com/rss/news/tennis/"),
    ("Sports.ru", "https://www.sports.ru/rss/rubric.xml?s=212"),
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/tennis/rss.xml"),
    ("The Guardian", "https://www.theguardian.com/sport/tennis/rss"),
    ("Sky Sports", "https://www.skysports.com/rss/12110"),
]
PER_SOURCE = 6
TOTAL = 24
MAX_AGE_DAYS = 14
OUT = Path(__file__).resolve().parent.parent / "news.json"
UA = "Mozilla/5.0 (compatible; DrTimingNewsBot/1.0; +https://foka756-creator.github.io/DR.TIMING/)"


def clean(text):
    text = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


# служебные объявления сайтов и заголовки с замаскированной бранью в бегущую строку не берём
SKIP = re.compile(r"#{2,}|\*{3,}|возобновил[аио]? работу|недоступн|технически[ех] работ", re.I)


def parse_date(value):
    try:
        d = parsedate_to_datetime(value)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch(name, url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        root = ET.fromstring(r.read())
    items = []
    for it in root.iter("item"):
        title = clean(it.findtext("title"))
        link = (it.findtext("link") or "").strip()
        date = parse_date(it.findtext("pubDate"))
        title = re.sub(r"^[^\w«\"“(]+", "", title)  # эмодзи и значки в начале
        if not title or SKIP.search(title) or not link.startswith(("http://", "https://")) or date is None:
            continue
        items.append({"title": title[:200], "link": link, "source": name, "published": date.astimezone(timezone.utc)})
    items.sort(key=lambda x: x["published"], reverse=True)
    return items[:PER_SOURCE]


def main():
    now = datetime.now(timezone.utc)
    pool, ok = [], 0
    for name, url in FEEDS:
        try:
            got = fetch(name, url)
            pool += got
            ok += 1
            print(f"ok   {name}: {len(got)}")
        except Exception as e:  # одна упавшая лента не ломает остальные
            print(f"FAIL {name}: {e}", file=sys.stderr)
    if ok == 0 or not pool:
        print("ни одна лента не ответила, news.json не меняю", file=sys.stderr)
        return 1
    fresh = [x for x in pool if now - x["published"] <= timedelta(days=MAX_AGE_DAYS)] or pool
    seen, result = set(), []
    for x in sorted(fresh, key=lambda x: x["published"], reverse=True):
        key = x["title"].lower()
        if key in seen or x["link"] in seen:
            continue
        seen.update((key, x["link"]))
        result.append({**x, "published": x["published"].strftime("%Y-%m-%dT%H:%M:%SZ")})
        if len(result) == TOTAL:
            break
    data = {"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "items": result}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"записано {len(result)} новостей")
    return 0


if __name__ == "__main__":
    sys.exit(main())
