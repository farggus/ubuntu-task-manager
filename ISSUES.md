# Issues & Known Problems

## Открытые проблемы

### 1. Избыточное DEBUG-логирование в fail2ban_v2

**Файл:** `src/collectors/fail2ban_v2.py`
**Строки:** 283, 288

**Описание:**
При запуске в режиме DEBUG в логи попадает огромное количество записей вида:
```
DEBUG - [utm.fail2ban_v2] - Recorded unban: 142.93.128.113 from sshd
DEBUG - [utm.fail2ban_v2] - Recorded ban: 142.93.128.113 from sshd
```

**Причина:**
1. Каждое событие ban/unban логируется отдельно с уровнем DEBUG
2. Архивные `.gz` файлы парсятся заново при каждом запуске (строка 208 пропускает только для не-gz файлов)

**Возможные решения:**
- Убрать пофайловое логирование, оставить только итоговую статистику
- Добавить отслеживание позиции для .gz файлов (или флаг "уже обработан")
- Использовать более низкий уровень логирования (TRACE) для массовых сообщений

---

### 2. System Information виджет долго грузится при запуске

**Файлы:**
- `src/collectors/system.py` (метод `collect()`, строки 38-58)
- `src/dashboard/widgets/system_info.py`

**Описание:**
При запуске приложения виджет System Information долго загружается (до 30+ секунд).

**Причина:**
Все операции сбора данных выполняются последовательно в `collect()`:
| Метод | Max время | Кэш |
|-------|-----------|-----|
| `_get_package_stats()` | 25 сек | 30 мин |
| `_get_smart_info()` | 60 сек (10с × диск × 6 попыток) | 5 мин |
| `_get_service_stats()` | 4 сек | нет |
| `_get_disk_info()` + lsblk | 5 сек | нет |

Первый запуск особенно медленный — все кэши пустые. Быстрые данные (CPU, RAM) ждут завершения медленных (packages, SMART).

**Возможные решения:**
1. Разделить на "быструю" и "медленную" фазы сбора данных
2. Предзагрузка кэшей в фоне при старте приложения
3. Отложенная загрузка тяжёлых данных (через 5-10 сек после старта)
4. Параллельный сбор данных в отдельных threads
5. Показывать placeholder "Loading..." для медленных секций

---

### 3. Table refresh failed: 'NoneType' object is not subscriptable

**Файл:** `src/dashboard/widgets/f2b_db_manage_modal.py`
**Строки:** 249-251

**Описание:**
При обновлении таблицы возникает ошибка:
```
ERROR - [utm.f2b_db_modal] - Table refresh failed: 'NoneType' object is not subscriptable
```

**Причина:**
Использование `dict.get(key, default)` не защищает от случая, когда ключ существует, но его значение равно `None`:
```python
geo = item.get("geo", {})       # Вернёт None, если geo=None в данных
geo.get("country", "?")         # None.get() → ошибка!
```

**Решение:**
Использовать `or` для защиты от None:
```python
geo = item.get("geo") or {}
attempts = item.get("attempts") or {}
bans = item.get("bans") or {}
```

---

### 4. Processes: "Running: 0" при первом открытии вкладки

**Файл:** `src/collectors/processes.py`
**Строка:** 34, 87

**Описание:**
При открытии вкладки "1 Processes" header показывает "Running: 0". После "^r Refresh All" значение нормализуется.

**Причина:**
`psutil.cpu_percent()` при **первом вызове** возвращает `0.0` для всех процессов (особенность psutil — нужен интервал для измерения).

Логика подсчёта "running" (строка 34):
```python
if status == STATUS_RUNNING or (cpu > 0.0 and status == STATUS_SLEEPING):
    stats['running'] += 1
```

При первом вызове `cpu = 0.0` для всех → sleeping процессы не считаются как "running".

**Решение:**
Добавить "прогрев" CPU счётчиков в `ProcessesCollector.__init__()`:
```python
def __init__(self, config=None):
    super().__init__(config)
    # Warm up CPU counters
    list(psutil.process_iter(['cpu_percent']))
```

---

### 5. Packages: "Update All" не обновляет все пакеты

**Файл:** `src/dashboard/widgets/packages.py`
**Строка:** 138

**Описание:**
После "U Update All" некоторые пакеты остаются необновлёнными (например, libnuma1, numactl, python3-distupgrade).

**Причина:**
1. Используется только `apt-get upgrade -y` без предварительного `apt update`
2. Индекс пакетов может быть устаревшим
3. Пакеты с новыми зависимостями могут быть "held back"

**Текущий код:**
```python
self.run_update_command([SUDO, APT_GET, "upgrade", "-y"])
```

**Решение:**
Выполнять `apt update` перед `apt upgrade`:
```python
# Вариант 1: одной командой через shell
self.run_update_command([SUDO, "sh", "-c", "apt-get update && apt-get upgrade -y"])

# Вариант 2: если held back пакеты всё ещё проблема — использовать dist-upgrade
self.run_update_command([SUDO, "sh", "-c", "apt-get update && apt-get dist-upgrade -y"])
```

**Примечание:** `dist-upgrade` более агрессивный — может удалить конфликтующие пакеты. Возможно стоит добавить предупреждение пользователю.

---

### 6. [Feature] Processes: сортировка по CPU% и клик по заголовкам

**Файл:** `src/dashboard/widgets/processes.py` (предположительно)

**Описание:**
Вкладка "1 Processes" — нужна сортировка таблицы процессов:
1. По умолчанию сортировать по "CPU%" (убывание)
2. Возможность сортировки кликом по заголовку колонки

**Текущее поведение:**
Таблица не сортирована или сортируется по другому критерию.

**Ожидаемое поведение:**
- При открытии вкладки — процессы отсортированы по CPU% (самые "тяжёлые" сверху)
- Клик по заголовку колонки — сортировка по этой колонке
- Повторный клик — обратная сортировка (asc/desc toggle)

**Реализация:**
Textual DataTable поддерживает `sort()` метод. Нужно:
1. Вызвать `table.sort("cpu_percent", reverse=True)` после загрузки данных
2. Добавить обработчик `on_data_table_header_selected` для сортировки по клику

---

## Решённые проблемы

(пусто)
