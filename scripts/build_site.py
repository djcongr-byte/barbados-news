#!/usr/bin/env python3
"""Static Barbados News portal: WordPress RSS announcements + all Telegraph links.
Python standard library only. Safe to rebuild automatically on GitHub Pages.
"""
from __future__ import annotations
import html
import hashlib
import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
CONFIG = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
REPOSITORY = os.getenv('GITHUB_REPOSITORY', 'djcongr-byte/barbados-news')
OWNER, REPO = (REPOSITORY.split('/', 1) + ['barbados-news'])[:2]
BASE = (os.getenv('SITE_URL') or CONFIG.get('site_url') or '').rstrip('/')
if not BASE:
    BASE = 'https://' + OWNER + '.github.io'
    if REPO.lower() != (OWNER + '.github.io').lower():
        BASE += '/' + REPO
BASE = BASE.rstrip('/')
TITLE = str(CONFIG.get('title', 'Barbados News'))
DESC = str(CONFIG.get('description', 'Новости криптовалют и библиотека публикаций Telegraph'))
WP = str(CONFIG.get('wordpress_url', 'https://barbados-news.com')).rstrip('/')
PER_PAGE = max(24, min(200, int(CONFIG.get('page_size', 80))))
NEWS_PAGE_SIZE = 12
NOW = datetime.now(timezone.utc)

CATEGORIES = [
    ('tron', 'TRON и TRX', r'\btron\b|\btrx\b|trc.?20', 'TRX', 'red'),
    ('bitcoin', 'Bitcoin и BTC', r'\bbitcoin\b|\bbtc\b|биткоин|lightning|satoshi|sat/vb', 'BTC', 'orange'),
    ('stablecoins', 'Стейблкоины', r'\busdt\b|\busdc\b|стейбл|stablecoin|\bdai\b|\bpyusd\b', 'USD', 'green'),
    ('security', 'Безопасность', r'безопас|мошен|взлом|скам|phishing|фишинг|поддел|seed|сид.фраз|приватн|хакер|уязвим', 'SEC', 'cyan'),
    ('wallets', 'Кошельки и переводы', r'кошел|wallet|адрес|перевод|txid|транзакц|мультиподпис', 'WAL', 'purple'),
    ('defi', 'DeFi и протоколы', r'\bdefi\b|ликвидн|uniswap|декс|\bdex\b|стейкинг|кредит|смарт.контракт', 'DeFi', 'blue'),
    ('trading', 'Биржи и торговля', r'бирж|трейд|торгов|курс|котиров|рынок|фьючерс|\brsi\b|свеч|скользящ', 'TRD', 'yellow'),
    ('altcoins', 'Другие криптовалюты', r'ethereum|эфириум|solana|polygon|toncoin|dogecoin|dash|litecoin|\bbnb\b|\bton\b', 'ALT', 'violet'),
]
CAT_MAP = {row[0]: row for row in CATEGORIES}
CAT_MAP['other'] = ('other', 'Другие темы', '', 'WEB3', 'gray')


def e(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def link(path=''):
    return BASE + '/' + str(path).lstrip('/')


def check_url(value, hosts):
    value = str(value or '').strip()
    p = urlparse(value)
    return value if p.scheme == 'https' and p.hostname in hosts else ''


def safe_image(value):
    value = str(value or '').strip()
    p = urlparse(value)
    if p.scheme == 'https' and p.netloc and len(value) < 1400:
        return value
    return ''


def load_json(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except (ValueError, OSError) as exc:
        print('WARNING reading JSON:', path, exc)
        return []


def category_for(title):
    for slug, name, pattern, icon, tone in CATEGORIES:
        if re.search(pattern, title, flags=re.I):
            return slug
    return 'other'


def telegraph_items():
    records = {}
    for x in load_json(ROOT / 'data' / 'articles.json'):
        if not isinstance(x, dict):
            continue
        url = check_url(x.get('url'), {'telegra.ph', 'www.telegra.ph'})
        if not url or not urlparse(url).path.strip('/'):
            continue
        title = re.sub(r'\s+', ' ', str(x.get('title') or x.get('topic') or urlparse(url).path.strip('/').replace('-', ' '))).strip()[:220]
        if not title:
            continue
        slug = category_for(title)
        records[url] = {
            'url': url, 'title': title,
            'date': str(x.get('date') or x.get('updated') or '')[:19],
            'category': CAT_MAP[slug][1], 'slug': slug,
            'source': 'telegraph',
        }
    return sorted(records.values(), key=lambda x: (x['date'], x['title']), reverse=True)


def wp_items():
    records = {}
    for x in load_json(ROOT / 'data' / 'barbados_feed.json'):
        if not isinstance(x, dict):
            continue
        url = check_url(x.get('url'), {'barbados-news.com', 'www.barbados-news.com'})
        if not url:
            continue
        title = re.sub(r'\s+', ' ', str(x.get('title') or '')).strip()[:220]
        if not title:
            continue
        records[url] = {
            'url': url, 'title': title,
            'date': str(x.get('date') or '')[:20],
            'category': re.sub(r'\s+', ' ', str(x.get('category') or 'Новости'))[:55],
            'description': re.sub(r'\s+', ' ', str(x.get('description') or '')).strip()[:230],
            'image': safe_image(x.get('image')),
            'source': 'wordpress',
        }
    return sorted(records.values(), key=lambda x: (x['date'], x['title']), reverse=True)

ARTICLES = telegraph_items()
NEWS = wp_items()
COUNTS = Counter(x['slug'] for x in ARTICLES)
ACTIVE_CATEGORIES = [CAT_MAP[slug] for slug, *_ in CATEGORIES if COUNTS[slug]]
if COUNTS['other']:
    ACTIVE_CATEGORIES.append(CAT_MAP['other'])


def day(raw):
    v = str(raw or '')[:10]
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
        return v[8:10] + '.' + v[5:7] + '.' + v[0:4]
    return ''


def favicon():
    return link('assets/favicon.svg')


def site_header(current='home'):
    menu = [
        ('home', 'Главная', ''),
        ('news', 'Новости BarbadosNews', 'news/'),
        ('archive', 'Telegraph', 'archive/'),
        ('topics', 'Рубрики', 'topics/'),
        ('tools', 'Инструменты', 'tools/'),
    ]
    nav = ''.join('<a class="nav-link%s" href="%s">%s</a>' %
                  (' active' if id == current else '', e(link(path)), e(title))
                  for id, title, path in menu)
    return '''<header class="site-header"><div class="shell header-inner">
<a class="brand" href="%s" aria-label="Barbados News — главная">
<span class="brand-symbol">B<span class="brand-spark">✦</span></span>
<span class="brand-words"><strong>Barbados<span>News</span></strong><small>Криптовалютные новости и аналитика</small></span></a>
<nav class="top-nav" aria-label="Основная навигация">%s</nav>
<div class="head-actions"><a class="header-search" href="%s" aria-label="Искать статьи">
<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/></svg><span>Поиск статей...</span><kbd>/</kbd></a>
<a class="head-cta" href="%s" target="_blank" rel="noopener noreferrer">Основной сайт <span aria-hidden="true">↗</span></a>
<button class="menu-toggle" type="button" aria-label="Открыть меню" aria-expanded="false" data-menu-toggle>☰</button></div>
</div></header>''' % (e(link('')), nav, e(link('search/')), e(WP))


def footer():
    year = NOW.year
    return '''<footer class="site-footer"><div class="shell footer-grid">
<div class="footer-about"><div class="footer-brand">Barbados<span>News</span></div>
<p>Свежие анонсы с BarbadosNews.com и библиотека публикаций Telegraph в одном месте.</p>
<span class="footer-legal">© %s BarbadosNews · Материалы носят информационный характер.</span></div>
<div class="footer-menu"><h3>Разделы</h3><a href="%s">Новости</a><a href="%s">Telegraph</a><a href="%s">Рубрики</a><a href="%s">Поиск</a></div>
<div class="footer-menu"><h3>BarbadosNews.com</h3><a href="%s">Криптоакадемия ↗</a><a href="%s">Проверка транзакций ↗</a><a href="%s">Календарь событий ↗</a><a href="%s">RSS новостей ↗</a></div>
<div class="footer-menu"><h3>Обновления</h3><p>Анонсы обновляются автоматически. Ссылки Telegraph синхронизируются с MultiAccount.</p>
<a class="footer-rss" href="%s">RSS этого каталога ↗</a></div></div></footer>''' % (
        year, e(link('news/')), e(link('archive/')), e(link('topics/')), e(link('search/')),
        e(WP + '/academy/'), e(WP + '/bitcoin-transaction-check/'),
        e(WP + '/crypto-calendar/'), e(WP + '/feed/'), e(link('feed.xml')))


def page(title, content, route='', description=DESC, current='home', image=''):
    canonical = link(route)
    page_title = (title + ' | Barbados News') if title != 'Barbados News' else title + ' — новости и криптобиблиотека'
    og_img = image or favicon()
    html_doc = '''<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title><meta name="description" content="%s"><meta name="theme-color" content="#061323">
<link rel="canonical" href="%s"><link rel="icon" type="image/svg+xml" href="%s">
<meta property="og:type" content="website"><meta property="og:title" content="%s">
<meta property="og:description" content="%s"><meta property="og:url" content="%s"><meta property="og:image" content="%s">
<link rel="alternate" type="application/atom+xml" title="Barbados News RSS" href="%s">
<link rel="stylesheet" href="%s"><script defer src="%s"></script></head><body>
%s<main id="main-content">%s</main>%s</body></html>''' % (
        e(page_title), e(description[:165]), e(canonical), e(favicon()), e(page_title),
        e(description[:165]), e(canonical), e(og_img), e(link('feed.xml')),
        e(link('assets/main.css')), e(link('assets/app.js')), site_header(current), content, footer())
    return html_doc


def write(path, content):
    full = OUT / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding='utf-8')


def topic_art(topic):
    topic = str(topic or '').lower()
    presets = [
        (r'bitcoin|биткоин|\bbtc\b', 'btc', '₿'),
        (r'ethereum|эфириум|\beth\b', 'eth', 'Ξ'),
        (r'tron|\btrx\b', 'tron', '◈'),
        (r'usdt|usdc|стейбл', 'usdt', '₮'),
        (r'защит|безопас|взлом|кошель|уязвим', 'safe', '✧'),
        (r'рынок|бирж|фьючерс|курс', 'market', '↗'),
    ]
    for pattern, name, symbol in presets:
        if re.search(pattern, topic, re.I):
            return name, symbol
    names = [('btc', '₿'), ('eth', 'Ξ'), ('tron', '◈'), ('usdt', '₮'), ('safe', '✧'), ('market', '↗')]
    return names[hashlib.sha256(topic.encode('utf-8')).digest()[0] % len(names)]


def thumb(url, class_name='', alt='', eager=False, topic=''):
    classes = 'news-thumb ' + class_name
    img = safe_image(url)
    if img:
        return '<div class="%s"><img src="%s" alt="%s" loading="%s" decoding="async"%s></div>' % (
            e(classes), e(img), e(alt), 'eager' if eager else 'lazy',
            ' fetchpriority="high"' if eager else '')
    art, symbol = topic_art(topic)
    return '<div class="%s placeholder-thumb art-%s" aria-hidden="true"><div class="holo-ring"></div><span class="holo-symbol">%s</span><span class="holo-lines"></span></div>' % (e(classes), e(art), e(symbol))


def news_card(item, compact=False):
    url = e(item['url'])
    if compact:
        return '''<a class="spotlight-row" href="%s" target="_blank" rel="noopener noreferrer">
%s<div class="spotlight-copy"><div class="eyebrow">BarbadosNews.com · %s</div><h3>%s</h3><span class="meta">%s <span class="meta-dot">•</span> Читать на сайте ↗</span></div></a>''' % (
            url, thumb(item['image'], 'spotlight-img', '', topic=item['title']), e(item['category']), e(item['title']), e(day(item['date'])))
    return '''<article class="article-card wp-card"><a href="%s" target="_blank" rel="noopener noreferrer" aria-label="%s">
%s<div class="article-info"><div class="card-label"><span class="pill source-wp">BarbadosNews.com</span><span class="text-quiet">%s</span></div>
<h3>%s</h3><p>%s</p><div class="card-bottom"><span>%s</span><span>Читать новость ↗</span></div></div></a></article>''' % (
        url, e(item['title']), thumb(item['image'], 'card-img', '', topic=item['title']), e(item['category']), e(item['title']),
        e(item['description'] or 'Полная публикация на BarbadosNews.com'), e(day(item['date'])))


def category_icon(slug):
    data = CAT_MAP[slug]
    return '<span class="cat-icon tone-%s" aria-hidden="true">%s</span>' % (e(data[4]), e(data[3]))


def telegraph_card(item):
    slug = item['slug']
    tone = CAT_MAP[slug][4]
    url = e(item['url'])
    return '''<article class="article-card tele-card"><a href="%s" target="_blank" rel="noopener noreferrer" aria-label="%s">
<div class="tele-visual tone-bg-%s"><div class="mesh-grid"></div><div class="tele-glow"></div>%s
<span class="tele-source">TELEGRAPH</span></div>
<div class="article-info"><div class="card-label"><span class="pill source-tele">Telegraph</span><span class="text-quiet">%s</span></div>
<h3>%s</h3><div class="card-bottom"><span>%s</span><span>Открыть ↗</span></div></div></a></article>''' % (
        url, e(item['title']), e(tone), category_icon(slug), e(item['category']), e(item['title']), e(day(item['date'])))


def topic_card(data):
    slug, name, pattern, icon, tone = data
    return '<a class="category-tile" href="%s">%s<span class="tile-label"><strong>%s</strong><small>%s публикаций</small></span><span class="tile-arrow">↗</span></a>' % (
        e(link('topics/' + slug + '/')), category_icon(slug), e(name), COUNTS[slug])


def section_heading(label, title, subtitle='', more='', more_label='Смотреть все'):
    return '<div class="section-heading"><div><div class="section-eyebrow">%s</div><h2>%s</h2>%s</div>%s</div>' % (
        e(label), e(title), ('<p>' + e(subtitle) + '</p>') if subtitle else '',
        ('<a class="section-link" href="%s">%s <span aria-hidden="true">↗</span></a>' % (e(more), e(more_label))) if more else '')


def tools_markup():
    tools = [
        ('Проверка транзакций', 'Отслеживание переводов и подтверждений', '/bitcoin-transaction-check/', '↗', 'electric'),
        ('Сети криптовалют', 'Сети, адреса и совместимость переводов', '/crypto-networks/', '◇', 'cyan'),
        ('Комиссии сетей', 'Инструменты для оценки комиссий', '/crypto-fees/', '≋', 'violet'),
        ('Календарь событий', 'Крипторынок и экономические даты', '/crypto-calendar/', '▦', 'orange'),
    ]
    result = ''
    for title, desc, path, icon, tone in tools:
        result += '''<a class="tool-tile" href="%s" target="_blank" rel="noopener noreferrer"><span class="tool-icon tool-%s">%s</span>
<span class="tool-text"><strong>%s</strong><small>%s</small></span><span class="tool-arrow">↗</span></a>''' % (
            e(WP + path), e(tone), e(icon), e(title), e(desc))
    return '<div class="tools-grid">' + result + '</div>'


def home():
    if NEWS:
        main = NEWS[0]
        hero_visual = thumb(main['image'], 'hero-picture', '', eager=True, topic=main['title'])
        hero = '''<a class="hero-story" href="%s" target="_blank" rel="noopener noreferrer">
%s<div class="hero-shade"></div><div class="hero-copy"><div class="hero-source"><span class="live-dot"></span>СВЕЖИЕ НОВОСТИ · BARBADOSNEWS.COM</div>
<h1>%s</h1><p>%s</p><div class="hero-footer"><span>%s</span><span class="hero-button">Читать новость <b>↗</b></span></div></div></a>''' % (
            e(main['url']), hero_visual, e(main['title']), e(main['description'] or 'Открыть свежую публикацию на основном сайте BarbadosNews.'), e(day(main['date'])))
        side = ''.join(news_card(x, True) for x in NEWS[1:4])
        if len(NEWS) == 1:
            side = '<div class="empty-side"><h3>Читайте материалы BarbadosNews</h3><a href="%s">Перейти к новостям ↗</a></div>' % e(WP)
    else:
        hero = '''<div class="hero-story hero-empty"><div class="hero-shade"></div><div class="hero-copy"><div class="hero-source">BARBADOS NEWS</div>
<h1>Новости криптовалют и ваши публикации в одном месте</h1>
<p>Анонсы основного сайта загрузятся автоматически из RSS. Каталог Telegraph остаётся доступным ниже.</p>
<div class="hero-footer"><a class="hero-button" href="%s">Открыть BarbadosNews ↗</a></div></div></div>''' % e(WP)
        side = '<div class="empty-side"><h3>Анонсы BarbadosNews</h3><p>После первого запуска GitHub Actions здесь появятся статьи из RSS.</p><a href="%s">Открыть RSS ↗</a></div>' % e(WP + '/feed/')
    if len(NEWS) > 4:
        more_news = '<div class="news-grid">' + ''.join(news_card(x) for x in NEWS[4:10]) + '</div>'
    elif NEWS:
        more_news = '<div class="news-grid">' + ''.join(news_card(x) for x in NEWS[1:4]) + '</div>'
    else:
        more_news = '<div class="message-panel">RSS автоматически проверяется при публикации сайта. После получения записей появятся карточки с реальными обложками и анонсами.</div>'
    intro = '''<section class="front-top"><div class="shell">
<div class="front-banner"><div><span class="status-chip"><span class="live-dot"></span> Обновляемая криптобиблиотека</span>
<span class="front-tagline">Один портал — два источника публикаций</span></div><div class="intro-stats"><span><b>%s</b> Telegraph</span><span class="stat-divider"></span><span><b>%s</b> анонсов BarbadosNews</span></div></div>
<div class="hero-layout">%s<aside class="spotlight-column"><div class="spotlight-heading"><strong>Также в новостях</strong><a href="%s">Все новости ↗</a></div>%s</aside></div>
</div></section>''' % (len(ARTICLES), len(NEWS), hero, e(link('news/')), side)
    cat_bar = '''<section class="shell feature-categories">%s<div class="category-grid">%s</div></section>''' % (
        section_heading('НАВИГАЦИЯ', 'Популярные рубрики', 'Публикации по криптовалютам, безопасности и рынку', link('topics/'), 'Все рубрики'),
        ''.join(topic_card(row) for row in ACTIVE_CATEGORIES[:6]))
    news_block = '''<section class="shell section-block" id="barbados-news">%s%s</section>''' % (
        section_heading('ИЗ BARBADOS-NEWS.COM', 'Свежие новости и анонсы', 'Настоящие заголовки, изображения и ссылки из WordPress RSS', link('news/'), 'Все новости'), more_news)
    tele_block = '''<section class="shell section-block tele-section" id="telegraph">%s<div class="tele-grid">%s</div>
<div class="section-bottom"><a class="button button-outline" href="%s">Все публикации Telegraph (%s) <span>↗</span></a>
<a class="subtle-link" href="%s">Искать по всему архиву →</a></div></section>''' % (
        section_heading('ПУБЛИКАЦИИ MULTIACCOUNT', 'Мои публикации Telegraph', 'Все старые ссылки сохранены. Новые добавляются автоматически из MultiAccount.', link('archive/'), 'Весь архив'),
        ''.join(telegraph_card(x) for x in ARTICLES[:12]) if ARTICLES else '<div class="message-panel">Ожидаются публикации из data/articles.json.</div>',
        e(link('archive/')), len(ARTICLES), e(link('search/')))
    tools = '''<section class="shell section-block tools-section">%s%s</section>''' % (
        section_heading('ПОЛЕЗНЫЕ СЕРВИСЫ', 'Инструменты BarbadosNews', 'Рабочие инструменты на вашем основном сайте', link('tools/'), 'Все инструменты'), tools_markup())
    promo = '''<section class="shell closing-banner"><div class="closing-glow"></div><span class="closing-kicker">BARBADOS NEWS × TELEGRAPH</span>
<h2>Новости и знания о криптовалютах — в одном месте</h2><p>Витрина свежих публикаций BarbadosNews и полный каталог Telegraph без потери ваших ссылок.</p>
<div class="closing-actions"><a class="button button-primary" href="%s">Открыть новости ↗</a><a class="button button-soft" href="%s">Библиотека Telegraph →</a></div></section>''' % (
        e(link('news/')), e(link('archive/')))
    return page('Barbados News', intro + cat_bar + news_block + tele_block + tools + promo,
                '', 'Новости криптовалют BarbadosNews.com, все ваши публикации Telegraph, категории и полезные инструменты.',
                'home', NEWS[0]['image'] if NEWS else '')


def pager(total, current, prefix, per_page):
    num = max(1, (total + per_page - 1) // per_page)
    if num <= 1:
        return ''
    def route(i):
        return prefix if i == 0 else prefix.rstrip('/') + '/page-' + str(i + 1) + '.html'
    buttons = []
    for i in range(num):
        if num > 12 and abs(current-i) > 2 and i not in (0, num-1):
            if i in (1, num-2):
                buttons.append('<span class="page-ellipsis">…</span>')
            continue
        label = str(i + 1)
        if i == current:
            buttons.append('<span aria-current="page" class="current">' + label + '</span>')
        else:
            buttons.append('<a href="' + e(link(route(i))) + '">' + label + '</a>')
    return '<nav class="pager" aria-label="Страницы">' + ''.join(buttons) + '</nav>'


def archive_page(items, heading, subtitle, route, current, label, source='telegraph', per_page=PER_PAGE, page_num=0):
    start = page_num * per_page
    listing = ''.join(news_card(x) if source == 'wordpress' else telegraph_card(x) for x in items[start:start+per_page])
    if not listing:
        listing = '<div class="message-panel">Публикаций пока нет. Попробуйте посмотреть другой раздел.</div>'
    cards_class = 'news-grid' if source == 'wordpress' else 'tele-grid archive-grid'
    description = subtitle + '. Всего материалов: ' + str(len(items)) + '.'
    content = '''<section class="shell inner-section"><div class="breadcrumbs"><a href="%s">Главная</a><span>›</span><span>%s</span></div>
<div class="archive-title"><div><div class="section-eyebrow">%s</div><h1>%s</h1><p>%s</p></div><div class="count-box"><strong>%s</strong><span>материалов</span></div></div>
<div class="archive-toolbar"><a class="button button-soft" href="%s">Поиск по всем статьям ↗</a>
%s</div><div class="%s">%s</div>%s</section>''' % (
        e(link('')), e(heading), e(label), e(heading if page_num == 0 else heading + ' — страница ' + str(page_num + 1)), e(subtitle),
        len(items), e(link('search/')), '<a class="text-quiet external-feed" href="' + e(WP + '/feed/') + '">RSS BarbadosNews ↗</a>' if source == 'wordpress' else '<span class="text-quiet">Ссылки открываются на Telegraph</span>',
        cards_class, listing, pager(len(items), page_num, route, per_page))
    page_route = route if page_num == 0 else route.rstrip('/') + '/page-' + str(page_num + 1) + '.html'
    file_path = (page_route + 'index.html') if page_route.endswith('/') else page_route
    write(file_path, page(heading, content, page_route, description, current))
    return file_path


def directory_page():
    content = '''<section class="shell inner-section"><div class="breadcrumbs"><a href="%s">Главная</a><span>›</span>Рубрики</div>
<div class="archive-title"><div><div class="section-eyebrow">КАТАЛОГ</div><h1>Все рубрики Telegraph</h1>
<p>Темы определяются по заголовкам автоматически, ссылки сохраняются в оригинальном виде.</p></div></div>
<div class="category-grid directory-grid">%s</div></section>''' % (
        e(link('')), ''.join(topic_card(x) for x in ACTIVE_CATEGORIES))
    write('topics/index.html', page('Все рубрики', content, 'topics/', current='topics'))


def tool_page():
    content = '''<section class="shell inner-section"><div class="breadcrumbs"><a href="%s">Главная</a><span>›</span>Инструменты</div>
<div class="archive-title"><div><div class="section-eyebrow">ИНСТРУМЕНТЫ</div><h1>Инструменты BarbadosNews</h1>
<p>Рабочие сервисы на вашем основном сайте. Ссылки открывают оригинальные инструменты.</p></div></div>%s</section>''' % (e(link('')), tools_markup())
    write('tools/index.html', page('Инструменты BarbadosNews', content, 'tools/', current='tools'))


def search_page():
    content = '''<section class="shell inner-section search-page"><div class="breadcrumbs"><a href="%s">Главная</a><span>›</span>Поиск</div>
<div class="archive-title"><div><div class="section-eyebrow">ЕДИНЫЙ ПОИСК</div><h1>Поиск по публикациям</h1>
<p>По всем заголовкам BarbadosNews и Telegraph. Поиск работает в браузере, без внешних сервисов.</p></div></div>
<div class="search-panel"><form id="global-search-form" role="search"><label class="sr-only" for="search-query">Поиск по заголовку</label>
<input id="search-query" type="search" autocomplete="off" placeholder="Например, USDT, TRON, Bitcoin, безопасность..." minlength="1">
<button class="button button-primary" type="submit">Найти ↗</button></form>
<div class="search-filters" role="group" aria-label="Источник статей"><button type="button" class="is-selected" data-source="all">Все источники</button><button type="button" data-source="wordpress">BarbadosNews.com</button><button type="button" data-source="telegraph">Telegraph</button></div>
<p id="search-hint" class="search-hint" aria-live="polite">Введите запрос, чтобы найти нужные публикации.</p></div>
<div id="search-results" class="search-results"></div></section>''' % e(link(''))
    write('search/index.html', page('Поиск публикаций', content, 'search/', current=''))


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    assets = ROOT / 'site_assets'
    dest = OUT / 'assets'
    if not assets.is_dir():
        raise RuntimeError('Missing site_assets directory')
    shutil.copytree(assets, dest)
    write('.nojekyll', '')
    paths = ['index.html']
    write('index.html', home())
    for page_num in range(max(1, (len(ARTICLES) + PER_PAGE-1) // PER_PAGE)):
        paths.append(archive_page(ARTICLES, 'Мои публикации Telegraph', 'Полный архив автоматически опубликованных материалов',
                                  'archive/', 'archive', 'БИБЛИОТЕКА', per_page=PER_PAGE, page_num=page_num))
    for page_num in range(max(1, (len(NEWS) + NEWS_PAGE_SIZE-1) // NEWS_PAGE_SIZE)):
        paths.append(archive_page(NEWS, 'Новости BarbadosNews.com', 'Анонсы из WordPress RSS с переходами на оригинальные статьи',
                                  'news/', 'news', 'НОВОСТИ', 'wordpress', NEWS_PAGE_SIZE, page_num))
    for info in ACTIVE_CATEGORIES:
        slug, name, *_ = info
        subset = [x for x in ARTICLES if x['slug'] == slug]
        for i in range(max(1, (len(subset) + PER_PAGE-1) // PER_PAGE)):
            paths.append(archive_page(subset, name, 'Материалы Telegraph в тематической рубрике',
                                      'topics/' + slug + '/', 'topics', 'РУБРИКА', per_page=PER_PAGE, page_num=i))
    directory_page()
    tool_page()
    search_page()
    paths += ['topics/index.html', 'tools/index.html', 'search/index.html']
    search_data = [
        {'title': x['title'], 'url': x['url'], 'date': day(x['date']), 'source': x['source'],
         'category': x['category']} for x in NEWS + ARTICLES
    ]
    write('search-index.json', json.dumps(search_data, ensure_ascii=False, separators=(',', ':')))
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in paths:
        path = path[:-len('index.html')] if path.endswith('index.html') else path
        sitemap.append('<url><loc>' + xml_escape(link(path)) + '</loc></url>')
    sitemap.append('</urlset>')
    write('sitemap.xml', '\n'.join(sitemap))
    write('robots.txt', 'User-agent: *\nAllow: /\nSitemap: ' + link('sitemap.xml') + '\n')
    feed = ['<?xml version="1.0" encoding="utf-8"?>', '<feed xmlns="http://www.w3.org/2005/Atom">',
            '<title>Barbados News — новости и Telegraph</title>', '<id>' + xml_escape(link('')) + '</id>',
            '<link href="' + xml_escape(link('feed.xml')) + '" rel="self"/>',
            '<updated>' + NOW.strftime('%Y-%m-%dT%H:%M:%SZ') + '</updated>']
    combined = sorted(NEWS + ARTICLES, key=lambda x: x['date'], reverse=True)[:50]
    for x in combined:
        raw_date = str(x['date'])
        pub_date = raw_date[:10] if re.match(r'^\d{4}-\d{2}-\d{2}', raw_date) else NOW.strftime('%Y-%m-%d')
        feed.extend(['<entry>', '<title>' + xml_escape(x['title']) + '</title>',
                     '<id>' + xml_escape(x['url']) + '</id>', '<link href="' + xml_escape(x['url'], {'"': '&quot;'}) + '"/>',
                     '<updated>' + pub_date + 'T00:00:00Z</updated>', '</entry>'])
    feed.append('</feed>')
    write('feed.xml', '\n'.join(feed))
    print('Built %s Telegraph links + %s WordPress announcements across %s HTML pages at %s' %
          (len(ARTICLES), len(NEWS), len(paths), BASE))

if __name__ == '__main__':
    main()
