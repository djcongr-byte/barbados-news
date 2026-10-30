# Barbados News — установка нового шаблона GitHub Pages

Сайт: https://djcongr-byte.github.io/barbados-news/  
Репозиторий: https://github.com/djcongr-byte/barbados-news

## Как установить архив

1. Скачайте ZIP и **распакуйте** его на компьютере.
2. Откройте: https://github.com/djcongr-byte/barbados-news/upload/main
3. Перетащите **содержимое распакованной папки**, а не сам ZIP. Должны загрузиться папки `.github`, `scripts`, `site_assets`, `data` и файлы `site.json`, `README.md`, `README_RU.md`.
4. Подтвердите замену старых `pages.yml`, `build_site.py` и `site.json` и нажмите **Commit changes**.
5. Проверьте вкладку Actions: https://github.com/djcongr-byte/barbados-news/actions — после успешной сборки откройте сайт.

Важно: `data/articles.json` отсутствует в архиве специально — **все ваши Telegraph-ссылки сохранятся**, новые продолжит добавлять MultiAccount. Не удаляйте этот файл при установке.

GitHub Pages **не распаковывает ZIP**, если просто загрузить его в репозиторий одним файлом. Загрузить нужно содержимое архива.

## Как это будет работать

- **Новости BarbadosNews** берутся автоматически из https://barbados-news.com/feed/ . Если доступен WordPress REST API, дополнительно извлекаются обложки и больше новостей. На GitHub Pages выводятся анонсы, ведущие на оригиналы.
- **Telegraph** берётся из вашего текущего `data/articles.json`. Старые адреса `/archive/` и `/topics/.../` остаются рабочими.
- **Поиск** охватывает оба источника, работает прямо в браузере.
- **Сборка сайта** запускается при новых публикациях MultiAccount, вручную или раз в час по расписанию. Расписание GitHub иногда выполняется с задержкой.
- **Отказ RSS** не удалит последнюю сохранённую подборку.
- **Реальные котировки** не выдумываются. На сайте есть ссылки на работающие инструменты BarbadosNews.

## Как обновить новости сразу

Откройте GitHub → Actions → **Build Barbados News portal** → **Run workflow** → выберите `main` → запустите. При этом будет проверен RSS.

## Технические файлы

- `scripts/fetch_wordpress.py` — загрузка и очистка RSS/REST.
- `scripts/build_site.py` — HTML, рубрики, поиск, RSS/Atom и sitemap.
- `site_assets/main.css` и `app.js` — оформление и интерактивный поиск.
- `.github/workflows/pages.yml` — автосборка и размещение GitHub Pages.
- `data/barbados_feed.json` — безопасный кеш анонсов (хранится в отдельном файле).

**Никаких токенов WordPress, серверов или плагинов устанавливать не требуется.**
