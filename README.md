# ⚡ DTEK Outage Monitor Bot

Telegram-бот для моніторингу аварійних відключень електроенергії ДТЕК у 4 регіонах України.

## 🔌 Можливості

- **Моніторинг 4 регіонів:** Київ, Київська область, Дніпропетровська область, Одеська область
- **Збереження адрес:** кожен користувач може зберегти до 10 адрес для моніторингу
- **Автоматична перевірка:** бот перевіряє сайти ДТЕК кожні 5 хвилин
- **Сповіщення:** автоматичне повідомлення при виявленні аварійного відключення за адресою користувача
- **Перевірка статусу:** можливість перевірити поточні відключення за своїми адресами

## 🛠 Технічний стек

| Технологія | Версія | Призначення |
|---|---|---|
| Python | 3.11 | Мова програмування |
| python-telegram-bot | 20.7 | Telegram Bot API (async) |
| Playwright | 1.40.0 | Парсинг сайтів ДТЕК (async) |
| asyncpg | 0.29.0 | PostgreSQL (async, connection pool) |
| APScheduler | 3.10.4 | Планувальник задач |
| python-dotenv | 1.0.0 | Змінні оточення |
| tenacity | 8.2.3 | Retry-логіка |

## 🚀 Встановлення та запуск локально

### 1. Клонування репозиторію

```bash
git clone https://github.com/Ivan200424/dtek-address-scraper.git
cd dtek-address-scraper
```

### 2. Створення `.env`

```bash
cp .env.example .env
# Відредагуйте .env, додайте свій TELEGRAM_BOT_TOKEN та параметри БД
```

### 3. Встановлення залежностей

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Створення PostgreSQL бази

```bash
createdb power_outage_bot
```

### 5. Ініціалізація бази даних

```bash
python init_db.py
```

### 6. Запуск бота

```bash
python main.py
```

## 🚂 Деплоймент на Railway

1. Створіть акаунт на [Railway](https://railway.app)
2. Створіть новий проєкт
3. Підключіть GitHub репозиторій
4. Додайте PostgreSQL сервіс
5. Налаштуйте змінні оточення:
   - `TELEGRAM_BOT_TOKEN` — токен вашого бота
   - `DATABASE_URL` — автоматично надається Railway при додаванні PostgreSQL
6. Railway автоматично збилдить і запустить бота через Dockerfile

## 🤖 Команди бота

| Команда | Опис |
|---|---|
| `/start` | Почати роботу з ботом |
| `/add_address` | Додати адресу для моніторингу |
| `/my_addresses` | Переглянути збережені адреси |
| `/delete_address` | Видалити адресу |
| `/status` | Перевірити поточні відключення |
| `/help` | Показати довідку |

## 📁 Структура проєкту

```
dtek-address-scraper/
├── main.py                          # Точка входу
├── init_db.py                       # Ініціалізація БД
├── requirements.txt                 # Залежності
├── Dockerfile                       # Docker конфігурація
├── Procfile                         # Railway/Heroku
├── railway.json                     # Railway конфігурація
├── nixpacks.toml                    # Nixpacks конфігурація
├── .env.example                     # Шаблон змінних оточення
├── config/
│   ├── settings.py                  # Налаштування бота
│   └── regions.py                   # Конфігурація регіонів ДТЕК
├── database/
│   ├── connection.py                # Підключення до PostgreSQL
│   ├── models.py                    # CRUD операції
│   └── migrations/
│       └── init.sql                 # SQL міграція
├── bot/
│   ├── handlers.py                  # Обробники команд
│   ├── keyboards.py                 # Клавіатури
│   └── messages.py                  # Текстові повідомлення
├── parsers/
│   ├── base_parser.py               # Базовий клас парсера
│   ├── kyiv_parser.py               # Парсер Київ
│   ├── kyiv_region_parser.py        # Парсер Київська область
│   ├── dnipro_parser.py             # Парсер Дніпро
│   └── odesa_parser.py              # Парсер Одеса
├── services/
│   ├── monitoring.py                # Сервіс моніторингу
│   ├── notification.py              # Сервіс сповіщень
│   └── address_matcher.py           # Порівняння адрес
└── utils/
    ├── logger.py                    # Налаштування логування
    └── helpers.py                   # Допоміжні функції
```

## ⚙️ Змінні оточення

| Змінна | Обов'язкова | За замовчуванням | Опис |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | — | Токен Telegram бота |
| `DATABASE_URL` | ❌ | — | URL підключення до PostgreSQL (пріоритет) |
| `DB_HOST` | ❌ | `localhost` | Хост PostgreSQL |
| `DB_PORT` | ❌ | `5432` | Порт PostgreSQL |
| `DB_NAME` | ❌ | `power_outage_bot` | Назва бази даних |
| `DB_USER` | ❌ | `postgres` | Користувач PostgreSQL |
| `DB_PASSWORD` | ❌ | — | Пароль PostgreSQL |
| `CHECK_INTERVAL` | ❌ | `300` | Інтервал перевірки (секунди) |
| `LOG_LEVEL` | ❌ | `INFO` | Рівень логування |
| `TZ` | ❌ | `Europe/Kiev` | Часова зона |
| `MAX_ADDRESSES_PER_USER` | ❌ | `10` | Максимум адрес на користувача |
| `BROWSER_TIMEOUT` | ❌ | `30` | Таймаут браузера (секунди) |

## 📄 Ліцензія

MIT
