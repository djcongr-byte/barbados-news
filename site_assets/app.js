(function () {
  'use strict';
  var menuToggle = document.querySelector('[data-menu-toggle]');
  var nav = document.querySelector('.top-nav');
  if (menuToggle && nav) {
    menuToggle.addEventListener('click', function () {
      var open = nav.classList.toggle('is-open');
      menuToggle.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        nav.classList.remove('is-open');
        menuToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  var searchInput = document.getElementById('search-query');
  var searchResults = document.getElementById('search-results');
  var form = document.getElementById('global-search-form');
  var hint = document.getElementById('search-hint');
  if (!searchInput || !searchResults || !form) {
    document.addEventListener('keydown', function (event) {
      var tag = document.activeElement ? document.activeElement.tagName : '';
      if (event.key === '/' && !/INPUT|TEXTAREA/.test(tag)) {
        var target = document.querySelector('.header-search');
        if (target) { event.preventDefault(); location.href = target.href; }
      }
    });
    return;
  }

  var base = document.querySelector('link[rel="canonical"]').href.replace(/search\/?$/, '');
  var params = new URLSearchParams(location.search);
  var items = [];
  var activeSource = ['wordpress', 'telegraph'].includes(params.get('source')) ? params.get('source') : 'all';
  var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-source]'));
  var query = params.get('q') || '';
  var maxVisible = 80;
  searchInput.value = query;

  function setSource(value) {
    activeSource = value;
    buttons.forEach(function (btn) {
      btn.classList.toggle('is-selected', btn.getAttribute('data-source') === value);
    });
    render();
  }
  buttons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      setSource(btn.getAttribute('data-source'));
    });
  });

  function normalize(s) {
    return String(s || '').toLocaleLowerCase('ru-RU').replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
  }
  function create(tag, className, value) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (typeof value === 'string') node.textContent = value;
    return node;
  }
  function render() {
    var q = normalize(query);
    var terms = q.split(' ').filter(Boolean);
    var filtered = items.filter(function (item) {
      if (activeSource !== 'all' && item.source !== activeSource) return false;
      if (!terms.length) return true;
      var haystack = normalize(item.title + ' ' + item.category);
      return terms.every(function (word) { return haystack.includes(word); });
    });
    searchResults.replaceChildren();
    if (!items.length) {
      hint.textContent = 'Загружается индекс публикаций…';
      return;
    }
    hint.textContent = q
      ? 'Найдено публикаций: ' + filtered.length + (filtered.length > maxVisible ? '. Показаны первые ' + maxVisible + '.' : '.')
      : 'Публикаций в выбранном источнике: ' + filtered.length + '. Введите запрос для поиска.';
    if (!filtered.length) {
      searchResults.appendChild(create('div', 'message-panel', 'Ничего не найдено. Попробуйте другое слово или выберите все источники.'));
      return;
    }
    filtered.slice(0, maxVisible).forEach(function (item) {
      var a = create('a', 'search-result');
      if (/^https:\/\//.test(item.url)) {
        a.href = item.url;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
      }
      var source = item.source === 'wordpress' ? 'BarbadosNews.com' : 'Telegraph';
      a.appendChild(create('div', 'eyebrow', source + ' · ' + item.category));
      a.appendChild(create('h3', '', item.title));
      a.appendChild(create('div', 'meta', (item.date || 'Без даты') + '   ·   Открыть публикацию ↗'));
      searchResults.appendChild(a);
    });
  }
  function updateUrl() {
    var url = new URL(location.href);
    if (query.trim()) url.searchParams.set('q', query.trim());
    else url.searchParams.delete('q');
    if (activeSource !== 'all') url.searchParams.set('source', activeSource);
    else url.searchParams.delete('source');
    history.replaceState(null, '', url.toString());
  }
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    query = searchInput.value;
    updateUrl();
    render();
  });
  var timer;
  searchInput.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      query = searchInput.value;
      updateUrl();
      render();
    }, 180);
  });
  setSource(activeSource);
  fetch(base + 'search-index.json', { cache: 'no-cache' })
    .then(function (res) { if (!res.ok) throw Error('HTTP ' + res.status); return res.json(); })
    .then(function (data) { items = Array.isArray(data) ? data : []; render(); })
    .catch(function () { hint.textContent = 'Индекс пока недоступен. Обновите страницу после публикации сайта.'; });

  document.addEventListener('keydown', function (event) {
    if (event.key === '/' && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
      event.preventDefault(); searchInput.focus();
    }
  });
})();
