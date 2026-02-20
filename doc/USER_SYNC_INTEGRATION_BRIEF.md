# Интеграция: API выгрузки пользователей для сервиса дерева

**Для:** разработчик сервиса построения дерева пользователей  
**Базовый URL:** `https://hardcode-it.store` (или `https://hardcode-it.ru`)

---

## Назначение

Магазин фиксирует создание и изменение пользователей в очереди. Ваш сервис может периодически забирать UUID из очереди и получать полные данные по каждому пользователю. Ключевое для дерева: связка **пользователь** → **наставник** (кто пригласил по реф-ссылке).

---

## Аутентификация

Все запросы требуют заголовок:

```
X-API-Key: <ключ>
```

Ключ выдаётся отдельно (контакт: _указать ответственного_).

---

## Схема работы

1. **Шаг 1.** Запросить список UUID изменённых пользователей.
2. **Шаг 2.** По каждому UUID запросить полные данные (один запрос или batch до 100 штук).
3. Для построения дерева использовать `uuid` и `referred_by_uuid`.

---

## Endpoints

### 1. Список UUID из очереди

```
GET https://hardcode-it.store/api/user-sync/
```

**Параметры:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `since`  | int | Unix time (секунды, UTC). Фильтр по `created_at >= since`. Опционально. |

**Ответ:**
```json
{
  "results": [
    "64e4cd2f-3e6a-4869-8c98-21b4cc9e1c71",
    "55b0cb2f-d0a1-4dd1-be83-740a6785a8cc"
  ]
}
```

---

### 2. Детали пользователя по UUID

```
GET https://hardcode-it.store/api/users/<uuid>/
```

**Ответ:**
```json
{
  "uuid": "64e4cd2f-3e6a-4869-8c98-21b4cc9e1c71",
  "referred_by_uuid": "55b0cb2f-d0a1-4dd1-be83-740a6785a8cc",
  "email": "user@example.com",
  "first_name": "Иван",
  "last_name": "Петров",
  "phone": "",
  "is_business_user": true,
  "is_active": true,
  "date_joined": "2026-02-04T08:51:14+00:00"
}
```

**Для дерева важны:**
- `uuid` — UUID пользователя
- `referred_by_uuid` — UUID наставника (пригласившего), `null` если корень дерева

---

### 3. Batch: несколько пользователей за запрос

```
GET https://hardcode-it.store/api/users/batch/?uuids=uuid1,uuid2,uuid3
```

Параметр `uuids` — через запятую, до 100 штук.

**Ответ:**
```json
{
  "results": [
    { "uuid": "...", "referred_by_uuid": "...", ... },
    { "uuid": "...", "referred_by_uuid": null, ... }
  ]
}
```

---

## Примеры запросов (cURL)

```bash
# 1. Список UUID (все из очереди)
curl -H "X-API-Key: YOUR_KEY" "https://hardcode-it.store/api/user-sync/"

# 2. Список UUID с момента 2026-01-01 00:00 UTC
curl -H "X-API-Key: YOUR_KEY" "https://hardcode-it.store/api/user-sync/?since=1735689600"

# 3. Детали одного пользователя
curl -H "X-API-Key: YOUR_KEY" "https://hardcode-it.store/api/users/64e4cd2f-3e6a-4869-8c98-21b4cc9e1c71/"

# 4. Batch (несколько пользователей)
curl -H "X-API-Key: YOUR_KEY" "https://hardcode-it.store/api/users/batch/?uuids=uuid1,uuid2,uuid3"
```

---

## Рекомендуемый алгоритм

1. Запускать синхронизацию по расписанию (например, каждые 5–10 минут).
2. `GET /api/user-sync/?since=<last_sync_timestamp>` — получить новые UUID.
3. Разбить UUID на пачки по 100 и запрашивать `GET /api/users/batch/?uuids=...`.
4. Обновлять дерево: для каждого пользователя добавить ребро `referred_by_uuid` → `uuid` (если `referred_by_uuid` не null).
5. Сохранить `last_sync_timestamp` для следующего цикла.

---

## Коды ошибок

| HTTP | Описание |
|------|----------|
| 401 | Нет или неверный X-API-Key |
| 404 | Пользователь с таким UUID не найден |
| 400 | Неверный параметр (например, `since` не число) |
