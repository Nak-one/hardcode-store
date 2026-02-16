# Отладка корзины — товары с вариантами

Логи пишутся в `logs/cart.log`. Просмотр в реальном времени:

```bash
tail -f /new_box/hardcode-store/logs/cart.log
```

## События

| Метка | Описание |
|-------|----------|
| `[get_cart]` | Чтение корзины из сессии. `session_key`, `raw_keys`, `is_new_format`, `result_keys` |
| `[set_cart]` | Сохранение корзины в сессию. `session_key`, `saving_keys` |
| `[add_from_catalog]` | Добавление товара с вариантами из каталога (плейсхолдер). `key`, `product_id` |
| `[add_from_detail]` | Добавление товара из карточки (вариант выбран). `key`, `product_id`, `variant_id` |
| `[replace_variant]` | Применение варианта к плейсхолдеру. `item_id`, `new_variant_id`, `cart_keys` |
| `[cart_replace]` | POST-обработчик. `item_id`, `new_variant_id`, `cart_keys before/after` |
| `[cart_add]` | Добавление в корзину. `product_id`, `variant_id`, `source`, `has_variants` |
| `[_render_cart]` | Отрисовка страницы корзины. `cart_keys`, `items_count`, `needs_selection` |

## Типичные проблемы

- **`item_id NOT IN cart`** — ключ из формы не найден в корзине. Возможны разные `session_key` (нет cookie).
- **`is_new_format=False`** — старая структура корзины, корзина очищается.
- **`replace_variant returned None`** — замена не прошла, смотри строки выше.
