# API выгрузки пользователей

Сервис дерева пользователей получает данные о пользователях по той же схеме, что и заказы.

## Схема работы

1. **Очередь изменений** — при создании/изменении/удалении User в БД ставится запись в `UserSyncQueue` (через сигналы).
2. **API #1** — получатель запрашивает список UUID пользователей из очереди.
3. **API #2** — по каждому UUID запрашивает полные данные пользователя.

Ключевые поля для построения дерева: **uuid** (пользователь) и **referred_by_uuid** (наставник).

---

## Аутентификация

Если в ` settings.USER_SYNC_API_KEY` задан ключ — все запросы должны содержать заголовок:

```
X-API-Key: <ключ>
```

или query-параметр `X-API-Key`. Иначе — 401.

---

## Endpoints

### 1. Список UUID из очереди

```
GET /api/user-sync/
GET /api/user-sync   (без слеша)
```

**Параметры:**
- `since` (опционально) — Unix time в секундах (UTC). Берутся записи с `created_at >= since`.

**Ответ:**
```json
{
  "results": ["uuid-1", "uuid-2", "uuid-3"]
}
```

---

### 2. Детали пользователя по UUID

```
GET /api/users/<uuid>/
GET /api/users/<uuid>
```

**Ответ:**
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "referred_by_uuid": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "email": "user@example.com",
  "first_name": "Иван",
  "last_name": "Петров",
  "phone": "+79001234567",
  "is_business_user": true,
  "is_active": true,
  "date_joined": "2026-01-15T14:30:00+00:00"
}
```

**Ключевые поля для дерева:**
- `uuid` — UUID пользователя
- `referred_by_uuid` — UUID наставника (кто пригласил по реф-ссылке), `null` если нет

---

### 3. Batch: несколько пользователей за запрос

```
GET /api/users/batch/?uuids=uuid1,uuid2,uuid3
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

## Пример работы получателя

```bash
# 1. Получить список UUID
curl -H "X-API-Key: YOUR_KEY" "https://site.example.com/api/user-sync/?since=1704067200"

# 2. Получить данные по UUID
curl -H "X-API-Key: YOUR_KEY" "https://site.example.com/api/users/550e8400-e29b-41d4-a716-446655440000/"

# 3. Batch
curl -H "X-API-Key: YOUR_KEY" "https://site.example.com/api/users/batch/?uuids=uuid1,uuid2,uuid3"
```

---

## Переменные окружения

В `.env`:

```
USER_SYNC_API_KEY=your-secret-api-key
```

Если не задан — проверка ключа не выполняется (небезопасно для продакшена).
