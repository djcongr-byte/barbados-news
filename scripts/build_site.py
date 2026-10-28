#!/usr/bin/env python3
"""Static, crawlable HTML catalog of published Telegraph pages (stdlib only)."""
from __future__ import annotations
import html
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '_site'
CONFIG = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
REPOSITORY = os.environ.get('GITHUB_REPOSITORY', 'example/telegraph-library')
OWNER, REPO = (REPOSITORY.split('/', 1) + ['telegraph-library'])[:2]
BASE_URL = os.environ.get('SITE_URL', '').strip().rstrip('/') or CONFIG.get('site_url', '').rstrip('/')
if not BASE_URL:
    if REPO.lower() == (OWNER + '.github.io').lower():
        BASE_URL = 'https://' + OWNER + '.github.io'
    else:
        BASE_URL = f'https://{OWNER}.github.io/{REPO}'
BASE_URL = BASE_URL.rstrip('/')
TITLE = str(CONFIG.get('title', 'Каталог криптоматериалов'))
DESCRIPTION = str(CONFIG.get('description', 'Подборка материалов о криптовалютах и блокчейне.'))
PER_PAGE = max(25, min(200, int(CONFIG.get('page_size', 80))))
CATEGORIES = [
    ('tron', 'TRON и TRX', r'\btron\b|\btrx\b|trc.?20'),
    ('bitcoin', 'Bitcoin и BTC', r'\bbitcoin\b|\bbtc\b|биткоин'),
    ('stablecoins', 'Стейблкоины', r'\busdt\b|\busdc\b|стейбл|stablecoin|\bdai\b'),
    ('security', 'Безопасность', r'безопас|мошен|взлом|скам|phishing|фишинг|поддел|seed|сид.фраз|приватн'),
    ('wallets', 'Кошельки и переводы', r'кошел|wallet|адрес|перевод|txid|транзакц'),
    ('defi', 'DeFi и протоколы', r'\bdefi\b|ликвидн|uniswap|декс|\bdex\b|стейкинг|кредит'),
    ('trading', 'Биржи и торговля', r'бирж|трейд|торгов|курс|котиров|рынок|фьючерс'),
    ('altcoins', 'Другие криптовалюты', r'ethereum|эфириум|solana|polygon|toncoin|dogecoin|dash|litecoin'),
]

def quote(t: str) -> str:
    return html.escape(str(t), quote=True)

def route_url(path: str) -> str:
    if path in ('', 'index.html'):
        return BASE_URL + '/'
    return BASE_URL + '/' + path

def detect_category(t: str) -> tuple[str, str]:
    for slug, name, pattern in CATEGORIES:
        if re.search(pattern, t, flags=re.I):
            return slug, name
    return 'other', 'Другие темы'

def sanitize(data: object) -> list[dict]:
    out: dict[str, dict] = {}
    for record in (data if isinstance(data, list) else []):
        if not isinstance(record, dict):
            continue
        link = str(record.get('url', '')).strip()
        parsed = urlparse(link)
        if parsed.scheme != 'https' or parsed.hostname not in ('telegra.ph', 'www.telegra.ph') or not parsed.path.strip('/'):
            continue
        title = str(record.get('title') or record.get('topic') or parsed.path.strip('/').replace('-', ' ')).strip()[:220]
        dt = str(record.get('date') or record.get('updated') or '')[:19]
        slug, category = detect_category(title)
        out[link] = {'url': link, 'title': title, 'date': dt, 'category_slug': slug, 'category': category}
    return sorted(out.values(), key=lambda x: (x['date'], x['title']), reverse=True)

ARTICLES = sanitize(json.loads((ROOT / 'data' / 'articles.json').read_text(encoding='utf-8')))

CSS = '''
:root{--ink:#121b30;--muted:#65748a;--blue:#2f64ee;--bg:#f6f8fc;--line:#dae2ef}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.container{max-width:1100px;margin:auto;padding:24px}header{background:#101b32;color:white;padding:22px 0}
header a{color:white;text-decoration:none}h1{font-size:clamp(1.7rem,3vw,2.7rem);line-height:1.2;margin:24px 0 10px}
h2{font-size:1.3rem}p{max-width:75ch}.lead{color:#53627a;font-size:1.06rem}
nav{display:flex;flex-wrap:wrap;gap:12px}nav a,.pill{display:inline-block;border:1px solid var(--line);padding:6px 12px;border-radius:999px;background:white;color:#1743a4;text-decoration:none}
a{color:#2459d5}a:hover{text-decoration:underline}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:20px 0}
.category{background:white;border:1px solid var(--line);padding:16px;border-radius:12px;text-decoration:none;color:var(--ink)}
.category strong{display:block}.category span,.meta{color:var(--muted);font-size:.88rem}
.items{list-style:none;margin:0;padding:0;background:white;border:1px solid var(--line);border-radius:14px;overflow:hidden}
.items li{padding:16px 20px;border-bottom:1px solid var(--line)}.items li:last-child{border-bottom:0}
.items a{font-weight:600;text-decoration:none}.items a:hover{text-decoration:underline}
small,footer{color:var(--muted)}footer{border-top:1px solid var(--line);margin-top:40px;padding:20px 0}
.pager{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}.pager a{padding:7px 12px;background:white;border:1px solid var(--line);border-radius:9px}
@media(max-width:620px){.container{padding:17px}.items li{padding:14px}}
'''

def page(title: str, content: str, canonical: str, description: str = DESCRIPTION) -> str:
    return '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' \
           f'<title>{quote(title)} — {quote(TITLE)}</title><meta name="description" content="{quote(description[:155])}">' \
           f'<link rel="canonical" href="{quote(canonical)}"><link rel="stylesheet" href="{quote(BASE_URL + "/assets/main.css")}">' \
           '</head><body><header><div class="container"><a href="' + quote(BASE_URL + '/') + '"><strong>' + quote(TITLE) + \
           '</strong></a></div></header><main class="container">' + content + \
           '</main><footer><div class="container">Тематический каталог внешних материалов. Включение ссылки не означает рекомендацию или независимую проверку фактов. ' \
           '<a href="' + quote(BASE_URL + '/feed.xml') + '">RSS/Atom</a></div></footer></body></html>'

def write(path: str, content: str) -> None:
    p = OUTPUT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding='utf-8')

def items_markup(items: list[dict]) -> str:
    if not items:
        return '<p>Пока нет опубликованных материалов.</p>'
    items_html = []
    for item in items:
        date = item['date'][:10]
        dt = f' · {quote(date)}' if date else ''
        items_html.append(f'<li><a href="{quote(item["url"])}" rel="noopener noreferrer">{quote(item["title"])}</a>'
                          f'<div class="meta">Telegraph{dt} · {quote(item["category"])}</div></li>')
    return '<ul class="items">' + ''.join(items_html) + '</ul>'

def pagination(items: list[dict], base: str, heading: str, desc: str) -> list[str]:
    count = max(1, (len(items) + PER_PAGE - 1) // PER_PAGE)
    pages = []
    for i in range(count):
        route = base if i == 0 else base.rstrip('/') + '/page-' + str(i + 1) + '.html'
        path = (route + 'index.html') if route.endswith('/') else (route or 'index.html')
        start = i * PER_PAGE
        end = min(len(items), (i + 1) * PER_PAGE)
        bar = '<div class="pager">'
        for j in range(count):
            if count > 25 and abs(j-i) > 2 and j not in (0, count-1):
                continue
            dest = base if j == 0 else base.rstrip('/') + '/page-' + str(j + 1) + '.html'
            bar += f'<a href="{quote(route_url(dest.strip("/")))}">{j + 1}</a>'
        bar += '</div>'
        title = heading if i == 0 else f'{heading} — страница {i + 1}'
        body = f'<h1>{quote(title)}</h1><p class="lead">{quote(desc)} Всего материалов: {len(items)}.</p>' + items_markup(items[start:end]) + bar
        write(path, page(title, body, route_url(route.strip('/'))))
        pages.append(path)
    return pages

def main() -> None:
    import shutil
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    write('assets/main.css', CSS)
    write('.nojekyll', '')
    counts = Counter(x['category_slug'] for x in ARTICLES)
    categories = [(slug, name, counts[slug]) for slug, name, pattern in CATEGORIES if counts.get(slug)]
    if counts.get('other'):
        categories.append(('other', 'Другие темы', counts['other']))
    cat_blocks = ''.join(f'<a class="category" href="{quote(route_url("topics/" + slug + "/"))}"><strong>{quote(name)}</strong><span>{count} материалов</span></a>' for slug,name,count in categories)
    intro = f'<h1>{quote(TITLE)}</h1><p class="lead">{quote(DESCRIPTION)}</p>'
    intro += '<p>Здесь собраны ссылки на опубликованные материалы в Telegraph. Каталог обновляется автоматически группами, не при каждой публикации.</p>'
    intro += '<h2>Разделы</h2><div class="grid">' + (cat_blocks or '<p>Разделы появятся после первой публикации.</p>') + '</div>'
    intro += '<h2>Последние публикации</h2>' + items_markup(ARTICLES[:PER_PAGE])
    intro += f'<p><a class="pill" href="{quote(route_url("archive/"))}">Открыть весь архив ({len(ARTICLES)})</a></p>'
    write('index.html', page(TITLE, intro, route_url('')))
    all_paths = ['index.html']
    all_paths += pagination(ARTICLES, 'archive/', 'Архив публикаций', 'Список опубликованных статей')
    for slug,name,count in categories:
        relevant = [x for x in ARTICLES if x['category_slug'] == slug]
        all_paths += pagination(relevant, 'topics/' + slug + '/', name, 'Материалы по теме')
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in all_paths:
        route = path[:-len('index.html')] if path.endswith('index.html') else path
        lines.append(f'<url><loc>{xml_escape(route_url(route))}</loc></url>')
    lines.append('</urlset>')
    write('sitemap.xml', '\n'.join(lines))
    write('robots.txt', 'User-agent: *\nAllow: /\nSitemap: ' + BASE_URL + '/sitemap.xml\n')
    feed = ['<?xml version="1.0" encoding="utf-8"?>', '<feed xmlns="http://www.w3.org/2005/Atom">',
            f'<title>{xml_escape(TITLE)}</title>', f'<id>{xml_escape(route_url(""))}</id>',
            f'<link href="{xml_escape(route_url("feed.xml"))}" rel="self"/>', f'<updated>{now}</updated>']
    for item in ARTICLES[:40]:
        date = item['date'][:10] if re.match(r'^\d{4}-\d{2}-\d{2}', item['date']) else now[:10]
        feed.extend(['<entry>', f'<title>{xml_escape(item["title"])}</title>', f'<id>{xml_escape(item["url"])}</id>',
                     f'<link href="{xml_escape(item["url"])}"/>', f'<updated>{date}T00:00:00Z</updated>', '</entry>'])
    feed.append('</feed>')
    write('feed.xml', '\n'.join(feed))
    print(f'Built {len(ARTICLES)} links across {len(all_paths)} crawlable pages at {BASE_URL}')

if __name__ == '__main__':
    main()
