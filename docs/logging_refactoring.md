# Fail2Ban Logging Refactoring

## Внесенные изменения

### Цель
Перевод отладочных логов Fail2Ban на правильные уровни логирования (DEBUG/INFO/WARNING) вместо использования INFO с префиксом `[BAN DEBUG]`.

### Файлы изменены
1. `src/collectors/fail2ban.py` - коллектор Fail2Ban данных
2. `src/dashboard/widgets/fail2ban.py` - виджет интерфейса Fail2Ban

## Новая структура логирования

### DEBUG (детальные шаги)
```python
logger.debug("Starting Fail2Ban data collection")
logger.debug(f"Processed jail '{jail_name}' in {duration:.3f}s")
logger.debug("IP validation passed for {ip}")
```

**Когда используется:**
- Начало операций (без времени)
- Обработка отдельных элементов (jail, IP)
- Промежуточные шаги

### INFO (важные события)
```python
logger.info(f"Banning IP {ip} in jail '{jail}'")
logger.info(f"Fail2Ban collection completed: {total_banned} banned IPs, ...")
logger.info(f"Successfully banned IP {ip} in {time:.2f}s")
```

**Когда используется:**
- Действия пользователя (ban/unban)
- Итоги операций с метриками
- Успешное завершение важных операций

### WARNING (медленные операции)
```python
if duration > 5.0:
    logger.warning(f"Slow jail processing: '{jail_name}' took {duration:.2f}s")
if duration > 10.0:
    logger.warning(f"Slow collector update took {duration:.2f}s")
```

**Когда используется:**
- Операции > 5 секунд (jail processing)
- Операции > 10 секунд (collector update)
- Неожиданные ситуации

### ERROR (ошибки)
```python
logger.error(f"Invalid IP address for ban: {ip}")
logger.error(f"Failed to ban IP {ip}: {e}")
```

**Когда используется:**
- Невалидные входные данные
- Исключения и ошибки выполнения

## Использование

### По умолчанию (production)
```bash
python src/main.py
```
**Результат:** Только INFO, WARNING, ERROR логи (без DEBUG)

### С отладкой (development)
```bash
python src/main.py --debug
```
**Результат:** Все уровни логов (DEBUG, INFO, WARNING, ERROR)

### Примеры вывода

**Без `--debug`:**
```
2026-01-27 20:35:05 - INFO - [utm.fail2ban_collector] - Fail2Ban collection completed: 185 banned IPs, 7 jails, duration=42.89s
2026-01-27 20:35:10 - INFO - [utm.fail2ban_tab] - Banning IP 192.168.1.100 in jail 'recidive'
2026-01-27 20:35:11 - INFO - [utm.fail2ban_collector] - Successfully banned IP 192.168.1.100 in 0.85s
```

**С `--debug`:**
```
2026-01-27 20:35:05 - DEBUG - [utm.fail2ban_collector] - Starting Fail2Ban data collection
2026-01-27 20:35:05 - DEBUG - [utm.fail2ban_collector] - fail2ban-client status executed in 0.123s
2026-01-27 20:35:05 - DEBUG - [utm.fail2ban_collector] - Found 7 active jails: ['recidive', 'sshd', 'samba', ...]
2026-01-27 20:35:18 - WARNING - [utm.fail2ban_collector] - Slow jail processing: 'recidive' took 12.86s
2026-01-27 20:35:29 - WARNING - [utm.fail2ban_collector] - Slow jail processing: 'sshd' took 10.95s
2026-01-27 20:35:46 - WARNING - [utm.fail2ban_collector] - Slow unban history parsing took 17.67s
2026-01-27 20:35:47 - INFO - [utm.fail2ban_collector] - Fail2Ban collection completed: 185 banned IPs, 7 jails, duration=42.89s
```

## Преимущества

✅ **Стандартная практика Python** - использование встроенных уровней логирования
✅ **Легкое управление** - включение/выключение через флаг `--debug`
✅ **Чистые логи** - убран redundant префикс `[BAN DEBUG]`
✅ **Автоматические предупреждения** - медленные операции выделяются WARNING
✅ **Совместимость** - работает со всеми стандартными инструментами логирования

## Обратная совместимость

Все изменения полностью обратно совместимы:
- Существующие конфиги работают без изменений
- Не требуется изменение скриптов запуска
- Поведение по умолчанию не изменилось
