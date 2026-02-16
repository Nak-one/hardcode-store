# Hardcode Store

Лендинг курса «Создать интернет-магазин» — третий сайт в связке с HardCore IT.

**Расположение проекта на сервере:** `/new_box/hardcode-store`. Здесь же будет жить бэкенд магазина (Node + PostgreSQL); отдельную базу для магазина нужно создать в уже установленном PostgreSQL — см. [doc/PLAN_INTERNET_MAGAZIN.md](doc/PLAN_INTERNET_MAGAZIN.md), раздел «База данных».

## Домен и SSL

- Сайт настроен в nginx на домен: **hardcode-it.ru** (и www).
- Чтобы он открывался по этому адресу:
  1. В DNS добавь A-запись: `hardcode-it.ru` → IP этого сервера (и при желании `www.hardcode-it.ru`).
  2. После того как DNS обновится, выдай SSL:
     ```bash
     sudo certbot --nginx -d hardcode-it.ru -d www.hardcode-it.ru --redirect --email tiptop7530@gmail.com
     ```

Пока домен не настроен, сайт можно смотреть по IP (если на 80 порту нет другого default) или позже по адресу https://hardcode-it.ru.

## Админка (Django)

- **URL:** https://hardcode-it.store/backend/ (путь `/backend/` вместо `/admin/` для снижения риска блокировки Safe Browsing).

## Содержимое

- **Главная** — герой «Создай свой интернет-магазин», программа (каталог, корзина, оплата, админка), блок «Записаться» с ссылкой на Telegram.
- Стиль в духе HardCore IT (тёмный фон, Anton, градиенты).
- Ссылка «Написать в Telegram» ведёт на `https://t.me/hardcore_it` — при необходимости поменяй в `index.html`.

## Файлы

- `index.html` — вся разметка и стили (одна страница).
