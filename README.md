# Car System Full Enhanced

Дипломен Flask проект за автосервиз.

## Ново в тази версия
- търсене по VIN, рег. номер, клиент и заглавие
- редакция на автомобили, части и работни поръчки
- PDF експорт на сервизна поръчка
- филтър по статус и статистика
- роли: manager, mechanic, client

## Стартиране
1. Инсталирай Python 3.11+
2. Отвори терминал в папката на проекта
3. Инсталирай зависимостите:

```bash
pip install -r requirements.txt
```

4. Стартирай:

```bash
python app.py
```

5. Отвори в браузър: `http://127.0.0.1:5000`

## Демо акаунти
- manager / manager123
- mechanic / mechanic123
- client / client123

## Забележка
SQLite базата се създава автоматично в `instance/car_service.sqlite3`.
