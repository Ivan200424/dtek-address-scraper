# ⚡ DTEK Outage Monitor Bot

Telegram bot for monitoring DTEK power outages in 4 regions of Ukraine. Built from scratch with AJAX-based queue detection.

## 🔌 Features

- **4 Regions Support:** Kyiv, Kyiv Oblast, Dnipropetrovsk Oblast, Odesa Oblast
- **102 Queues:** Full support for all outage queues (66 Kyiv + 12×3 other regions)
- **AJAX Queue Detection:** Direct API calls to DTEK for accurate queue numbers
- **Save Addresses:** Up to 10 addresses per user
- **Auto-Monitoring:** Checks DTEK sites every 5 minutes
- **Instant Notifications:** Alerts when new outages are detected
- **Status Checking:** Check current outages for your addresses

## 🛠 Technology Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Programming language |
| python-telegram-bot | 20.7 | Telegram Bot API (async) |
| Playwright | 1.40.0 | Web scraping with AJAX support |
| asyncpg | 0.29.0 | PostgreSQL (async, connection pool) |
| APScheduler | 3.10.4 | Task scheduler |
| python-dotenv | 1.0.0 | Environment variables |

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 13+
- Telegram Bot Token (get from [@BotFather](https://t.me/botfather))

### Local Installation

1. **Clone the repository:**

```bash
git clone https://github.com/Ivan200424/dtek-address-scraper.git
cd dtek-address-scraper
```

2. **Create virtual environment:**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**

```bash
pip install -r requirements.txt
playwright install chromium
```

4. **Setup database:**

```bash
createdb dtek_bot
```

5. **Configure environment:**

```bash
cp .env.example .env
# Edit .env with your settings:
# - TELEGRAM_BOT_TOKEN
# - DATABASE_URL
```

6. **Run the bot:**

```bash
python main.py
```

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

1. **Clone and configure:**

```bash
git clone https://github.com/Ivan200424/dtek-address-scraper.git
cd dtek-address-scraper
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN
```

2. **Start services:**

```bash
docker-compose up -d
```

3. **View logs:**

```bash
docker-compose logs -f bot
```

4. **Stop services:**

```bash
docker-compose down
```

### Using Docker only

```bash
docker build -t dtek-bot .
docker run -d \
  --name dtek-bot \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  dtek-bot
```

## 🚂 Railway Deployment

1. Create account on [Railway](https://railway.app)
2. Create new project from GitHub repo
3. Add PostgreSQL service
4. Set environment variables:
   - `TELEGRAM_BOT_TOKEN` - your bot token
   - `DATABASE_URL` - automatically provided by Railway
5. Deploy!

Railway will automatically build using the Dockerfile.

## 🤖 Bot Commands

| Command | Description |
|---|---|
| `/start` | Start working with the bot |
| `/add_address` | Add address for monitoring |
| `/my_addresses` | View saved addresses |
| `/delete_address` | Delete an address |
| `/status` | Check current outages |
| `/help` | Show help information |

## 📱 Usage Flow

1. **Start bot:** `/start`
2. **Add address:** Click "📍 Додати адресу" button
3. **Select region:** Choose from 4 available regions
4. **Enter city:** For regions other than Kyiv (with prefix: м., с., смт., с-ще.)
5. **Enter street:** With prefix (вул., просп., пров., пл., б-р.)
6. **Enter building:** House number
7. **Queue detection:** Bot automatically gets queue number via AJAX
8. **Confirm:** Click "✅ Підтвердити" to save
9. **Monitor:** Bot checks every 5 minutes and notifies about outages

## 📁 Project Structure

```
dtek-address-scraper/
├── main.py                    # Entry point
├── requirements.txt           # Dependencies
├── Dockerfile                 # Docker configuration
├── docker-compose.yml         # Docker Compose setup
├── .env.example               # Environment template
├── README.md                  # Documentation
├── config/
│   ├── __init__.py
│   ├── settings.py            # Settings from .env
│   └── regions.py             # Regions and queues configuration
├── bot/
│   ├── __init__.py
│   ├── handlers.py            # Telegram command handlers
│   ├── keyboards.py           # Keyboard layouts
│   └── messages.py            # Text messages
├── database/
│   ├── __init__.py
│   ├── connection.py          # PostgreSQL connection
│   ├── models.py              # CRUD operations
│   └── migrations/
│       └── init.sql           # Database initialization
├── services/
│   ├── __init__.py
│   ├── queue_checker.py       # AJAX-based queue detection
│   ├── outage_checker.py      # Outage monitoring
│   ├── notifier.py            # User notifications
│   └── monitoring.py          # Periodic monitoring
├── parsers/
│   ├── __init__.py
│   └── dtek_parser.py         # DTEK website parser
└── utils/
    ├── __init__.py
    └── helpers.py             # Utility functions
```

## 🔧 How Queue Detection Works

The bot uses a direct AJAX approach (not form filling) to get accurate queue numbers:

1. **Open DTEK page** via Playwright
2. **Extract CSRF token** from `<meta name="csrf-token">`
3. **POST to `/ua/ajax`** with:
   - `method=getHomeNum`
   - Address data (city, street, building)
   - `updateFact` with current datetime
4. **Parse JSON response** to extract queue number from `group` field

This approach is based on how real DTEK websites work and provides accurate results.

## 🗺 Supported Regions & Queues

### Kyiv — 66 queues
- **Standard:** 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 5.1, 5.2, 6.1, 6.2
- **Extended:** 7.1 to 60.1 (54 additional queues)

### Kyiv Oblast — 12 queues
1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 5.1, 5.2, 6.1, 6.2

### Dnipropetrovsk Oblast — 12 queues
1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 5.1, 5.2, 6.1, 6.2

### Odesa Oblast — 12 queues
1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 5.1, 5.2, 6.1, 6.2

**Total: 102 queues**

## 🔍 Key Improvements

This rebuild includes critical fixes:

1. **AJAX Queue Detection:** Direct API calls instead of unreliable form filling
2. **Fixed Confirm Button:** Proper `context.user_data` handling in ConversationHandler
3. **Database Schema:** `queue_number` column in main CREATE TABLE
4. **All 102 Queues:** Full support for Kyiv's extended 66 queues
5. **Proper Error Handling:** Graceful fallback when queue detection fails

## 📝 Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Telegram bot token |
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `DB_POOL_MIN_SIZE` | No | 2 | Min database connections |
| `DB_POOL_MAX_SIZE` | No | 10 | Max database connections |
| `CHECK_INTERVAL` | No | 300 | Check interval in seconds |
| `MAX_ADDRESSES_PER_USER` | No | 10 | Max addresses per user |
| `LOG_LEVEL` | No | INFO | Logging level |
| `TZ` | No | Europe/Kyiv | Timezone |
| `PLAYWRIGHT_TIMEOUT` | No | 60000 | Playwright timeout (ms) |

## 🐛 Troubleshooting

### Bot doesn't start
- Check `TELEGRAM_BOT_TOKEN` in `.env`
- Verify PostgreSQL is running
- Check database connection string

### Queue number always "невідомо"
- Ensure Playwright browsers are installed: `playwright install chromium`
- Check DTEK website is accessible
- Review logs for AJAX request errors

### Database errors
- Run migrations: `python -c "import asyncio; from database.connection import Database; asyncio.run(Database().init_tables())"`
- Check PostgreSQL version (13+ recommended)

## 📜 License

MIT License - feel free to use and modify.

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📧 Support

For issues and questions, please open an issue on GitHub.

## ⭐ Star History

If you find this bot useful, please consider giving it a star! ⭐
