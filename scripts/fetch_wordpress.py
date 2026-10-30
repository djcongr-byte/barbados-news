#!/usr/bin/env python3
"""Fetch public BarbadosNews RSS and optional WP REST metadata to a durable cache.
No tokens or third-party dependencies. Failure preserves the previous snapshot.
"""
from __future__ import annotations
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
CACHE = ROOT / 'data' / 'barbados_feed.json'
BASE = str(CONFIG.get('wordpress_url', 'https://barbados-news.com')).rstrip('/')
FEED_URL = str(CONFIG.get('wordpress_feed', BASE + '/feed/'))
LIMIT = max(12, min(75, int(CONFIG.get('news_limit', 48))))
HOSTS = {'barbados-news.com', 'www.barbados-news.com'}
MEDIA = '{http://search.yahoo.com/mrss/}'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}'

class HTMLReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.images = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'script', 'style'}:
            self.ignored += 1
        if tag == 'img':
            for key in ('data-src', 'data-lazy-src', 'src'):
                v = attrs.get(key)
                if v and not v.startswith(('data:', 'blob:')):
                    self.images.append(v)
                    break
            if not self.images and attrs.get('srcset'):
                self.images.append(attrs['srcset'].split(',')[-1].strip().split()[0])
        if tag in {'p', 'div', 'li', 'br'}:
            self.text.append(' ')

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.ignored = max(0, self.ignored - 1)
        if tag in {'p', 'div', 'li'}:
            self.text.append(' ')

    def handle_data(self, data):
        if not self.ignored:
            self.text.append(data)


def strip_tags(raw):
    reader = HTMLReader()
    reader.feed(raw or '')
    return re.sub(r'\s+', ' ', html.unescape(' '.join(reader.text))).strip(), reader.images


def normalize_url(raw, base=BASE, require_own=False):
    if not raw:
        return ''
    url = urljoin(base + '/', html.unescape(str(raw).strip()))
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or (require_own and parsed.hostname.lower() not in HOSTS):
        return ''
    return url


def fetch_bytes(url, timeout=22, max_bytes=6_000_000):
    req = Request(url, headers={
        'User-Agent': 'BarbadosNews-StaticIndex/2.0 (+https://djcongr-byte.github.io/barbados-news/)',
        'Accept': 'application/rss+xml, application/xml, application/json;q=0.9, */*;q=0.5',
    })
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f'HTTP {response.status}: {url}')
        payload = response.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise RuntimeError(f'Response too large: {url}')
        return payload


class OpenGraphReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.image = ''

    def handle_starttag(self, tag, attrs):
        if tag != 'meta' or self.image:
            return
        attrs = dict(attrs)
        key = (attrs.get('property') or attrs.get('name') or '').lower()
        if key in {'og:image', 'og:image:secure_url', 'twitter:image'}:
            self.image = normalize_url(attrs.get('content'))


def wordpress_page_image(url):
    try:
        page = fetch_bytes(url, timeout=8, max_bytes=2_000_000)
        reader = OpenGraphReader()
        reader.feed(page.decode('utf-8', errors='replace'))
        return reader.image
    except Exception:
        return ''


def date_iso(raw):
    if not raw:
        return ''
    raw = str(raw).strip()
    try:
        date = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        try:
            date = parsedate_to_datetime(raw)
        except (ValueError, TypeError, IndexError):
            return ''
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def image_from_xml(item):
    for name in (MEDIA + 'content', MEDIA + 'thumbnail', 'enclosure'):
        for el in item.findall(name):
            candidate = el.attrib.get('url')
            media_type = el.attrib.get('type', '')
            if candidate and (name != 'enclosure' or media_type.startswith('image/')):
                valid = normalize_url(candidate)
                if valid:
                    return valid
    for source in (item.findtext(CONTENT + 'encoded'), item.findtext('description')):
        _, images = strip_tags(source or '')
        for src in images:
            valid = normalize_url(src)
            if valid:
                return valid
    return ''


def parse_feed(payload):
    root = ET.fromstring(payload)
    entries = []
    for item in root.findall('.//channel/item'):
        link = normalize_url(item.findtext('link'), require_own=True)
        title, _ = strip_tags(item.findtext('title') or '')
        if not link or not title:
            continue
        summary, _ = strip_tags(item.findtext('description') or '')
        if not summary:
            summary, _ = strip_tags(item.findtext(CONTENT + 'encoded') or '')
        categories = [strip_tags(x.text or '')[0] for x in item.findall('category')]
        entries.append({
            'url': link,
            'title': title[:220],
            'date': date_iso(item.findtext('pubDate')),
            'description': summary[:280],
            'category': next((x for x in categories if x), 'Новости'),
            'image': image_from_xml(item),
        })
    return entries


def parse_rest(payload):
    raw = json.loads(payload.decode('utf-8-sig'))
    if not isinstance(raw, list):
        return []
    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        link = normalize_url(item.get('link'), require_own=True)
        title, _ = strip_tags((item.get('title') or {}).get('rendered', ''))
        if not link or not title:
            continue
        summary, _ = strip_tags((item.get('excerpt') or {}).get('rendered', ''))
        if not summary:
            summary, _ = strip_tags((item.get('content') or {}).get('rendered', ''))
        image = ''
        embedded = (item.get('_embedded') or {}).get('wp:featuredmedia') or []
        if embedded and isinstance(embedded[0], dict):
            image = normalize_url(embedded[0].get('source_url'))
        if not image:
            content_html = (item.get('content') or {}).get('rendered', '')
            _, images = strip_tags(content_html)
            image = next((normalize_url(src) for src in images if normalize_url(src)), '')
        entries.append({
            'url': link, 'title': title[:220],
            'date': date_iso(item.get('date_gmt') or item.get('date')),
            'description': summary[:280],
            'category': 'Новости', 'image': image,
        })
    return entries


def normalize(items):
    result = {}
    for item in items:
        if item['url'] not in result:
            result[item['url']] = item
        else:
            old = result[item['url']]
            for field in ('image', 'description', 'category', 'date'):
                if not old.get(field) or (field == 'category' and old[field] == 'Новости'):
                    old[field] = item.get(field, old.get(field, ''))
    return sorted(result.values(), key=lambda x: (x['date'], x['url']), reverse=True)[:LIMIT]


def main():
    errors = []
    rss = []
    rest = []
    try:
        rss = parse_feed(fetch_bytes(FEED_URL))
        print(f'WordPress RSS: {len(rss)} entries')
    except Exception as exc:
        errors.append(f'RSS unavailable: {exc}')
    api = BASE + '/wp-json/wp/v2/posts?per_page=' + str(LIMIT) + '&_embed=wp:featuredmedia'
    try:
        rest = parse_rest(fetch_bytes(api))
        print(f'WordPress REST: {len(rest)} entries')
    except Exception as exc:
        errors.append(f'REST unavailable: {exc}')
    if not rss and not rest:
        for line in errors:
            print('WARNING:', line, file=sys.stderr)
        print('No new articles received; preserving cache')
        return 0
    old_items = []
    if CACHE.exists():
        try:
            old_items = json.loads(CACHE.read_text(encoding='utf-8'))
            if not isinstance(old_items, list):
                old_items = []
        except (ValueError, OSError):
            old_items = []
    # Keep previously indexed URLs when REST briefly fails or RSS exposes only ten posts.
    merged = normalize(rss + rest + old_items)
    if not merged:
        print('WARNING: No usable WordPress entries, preserving cache', file=sys.stderr)
        return 0
    # Featured images are not always included in RSS. Try og:image on a few newest
    # article pages, using a small bounded worker pool; never block publication.
    missing = [x for x in merged[:10] if not x.get('image')]
    if missing:
        with ThreadPoolExecutor(max_workers=3) as pool:
            images = list(pool.map(wordpress_page_image, [x['url'] for x in missing]))
        for item, image in zip(missing, images):
            if image:
                item['image'] = image
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    updated = json.dumps(merged, ensure_ascii=False, indent=2) + '\n'
    if not CACHE.exists() or CACHE.read_text(encoding='utf-8') != updated:
        CACHE.write_text(updated, encoding='utf-8')
        print(f'Updated cache with {len(merged)} WordPress posts')
    else:
        print(f'Cache unchanged ({len(merged)} WordPress posts)')
    for line in errors:
        print('NOTE:', line, file=sys.stderr)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
