# Перенос контента Hardcode Store на другой сервер

Сюда выгружается каталог (товары, категории, бренды, атрибуты), справочник городов и **пользователи** (учётные записи и сохранённые адреса). **Заказы и корзины не переносятся.**

---

## На текущем (исходном) сервере

1. Выгрузить данные в фикстуру:
   ```bash
   cd /path/to/hardcode-store
   source .venv/bin/activate
   python manage.py dump_deploy_data
   ```
   Будет создан файл `deploy_data/fixture.json`.

2. (Опционально) Упаковать медиа-файлы товаров, чтобы перенести изображения:
   ```bash
   zip -r deploy_data/media_products.zip media/products/
   ```

3. Перенести в новое место:
   - папку `deploy_data/` (как минимум `fixture.json`);
   - при необходимости архив с медиа и/или папку `media/products/`.

---

## На новом сервере (развёртывание)

1. Клонировать репозиторий и настроить окружение:
   ```bash
   git clone https://github.com/Nak-one/hardcode-store.git
   cd hardcode-store
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Создать БД и `.env`:
   ```bash
   cp .env.example .env
   # Отредактировать .env: DB_*, SECRET_KEY, при необходимости CDEK_*, FIVEPOST_*, RUSSIANPOST_SENDER_INDEX
   ```

3. Миграции и загрузка фикстуры:
   ```bash
   python manage.py migrate
   python manage.py loaddata deploy_data/fixture.json
   ```

4. (Если переносили медиа) Распаковать изображения товаров:
   ```bash
   unzip deploy_data/media_products.zip -d .
   # или скопировать media/products/ в MEDIA_ROOT
   ```

5. Суперпользователь и запуск:
   ```bash
   python manage.py createsuperuser
   python manage.py collectstatic --noinput
   python manage.py runserver
   ```

После этого в новом проекте будут те же категории, товары, варианты, города и пользователи (логин по email; пароли переносятся в хешированном виде). Заказы нужно создавать заново.
