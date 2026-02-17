# Testing Guide for Queue Detection Fixes

## Changes Made

### 1. Critical Fixes to `services/queue_checker.py`

✅ **Added User-Agent to browser context:**
```python
user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
```
This prevents DTEK's WAF/anti-bot protection from blocking requests.

✅ **Changed wait strategy from "load" to "networkidle":**
```python
await page.goto(base_url, timeout=NAVIGATION_TIMEOUT, wait_until="networkidle")
```
This ensures all JavaScript and AJAX calls complete before we try to interact with the page.

✅ **Added retry logic with exponential backoff:**
- Up to 3 attempts
- Initial delay: 2 seconds
- Exponential backoff (2x multiplier)
- Retries on transient errors, skips retries on "no_retry" errors (e.g., building not found)

✅ **Changed return type to dict with error details:**
```python
# Before: Optional[str] - returns queue number or None
# After: Dict[str, Any] - returns {"queue": "3.1", "error": None} or {"queue": None, "error": "reason"}
```

✅ **Added suspect HTML detection:**
Checks if the page content is too small (< 1000 bytes) which could indicate blocking or errors.

### 2. Enhanced Error Reporting in `bot/handlers.py`

✅ **Updated `building_entered` handler to show error details:**
```python
if queue_number:
    queue_info = f"🔢 Черга відключення: {queue_number}"
elif error:
    queue_info = f"🔢 Черга відключення: невідомо\n⚠️ Причина: {error}"
```

Now users will see WHY queue detection failed, not just "невідомо".

✅ **Added `/debug` command:**
New command that tests:
1. Can Playwright launch?
2. Can we reach dtek-krem.com.ua?
3. Can we get CSRF token?
4. Can getStreet API work?

Users can run `/debug` from their phone to diagnose issues without access to server logs.

### 3. Created `services/queue_from_github.py`

✅ **Fallback data source from GitHub:**
- Fetches schedule data from `Baskerville42/outage-data-ua` repository
- Updates every 5 minutes
- Can be used to verify queue numbers
- NOTE: Currently a stub - the actual GitHub data format is more complex than initially designed

## How to Test

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (REQUIRED!)
playwright install chromium

# Or use Docker
docker-compose up -d
```

### Test 1: Manual queue detection test

```bash
cd /home/runner/work/dtek-address-scraper/dtek-address-scraper

python << 'EOF'
import asyncio
from services.queue_checker import get_queue_number

async def test():
    # Test case from problem statement
    # Expected: queue 3.1 for this address
    result = await get_queue_number(
        region_key='kyiv_region',
        city='с. Нижча Дубечня',
        street='вул. Деснянська',
        building='1'
    )
    
    print(f"Queue: {result['queue']}")
    print(f"Error: {result['error']}")

asyncio.run(test())
EOF
```

### Test 2: Start the bot and use `/debug` command

```bash
# Set up environment
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN

# Run bot
python main.py

# In Telegram:
# 1. /start
# 2. /debug  - This will run diagnostic tests
```

### Test 3: Add an address through the bot

```bash
# In Telegram:
# 1. /start
# 2. Click "📍 Додати адресу"
# 3. Select "Київська область"
# 4. Enter city: Нижча Дубечня (without prefix is OK now)
# 5. Enter street: Деснянська (without prefix is OK now)
# 6. Enter building: 1
# 7. Wait for queue detection
# 8. Check if you see either:
#    - "🔢 Черга відключення: 3.1" (SUCCESS!)
#    - "🔢 Черга відключення: невідомо\n⚠️ Причина: ..." (with error details)
```

## Expected Behavior Changes

### Before (Broken):
- User enters address
- Bot always shows "🔢 Черга відключення: невідомо"
- No information about what went wrong
- User has no way to diagnose the issue

### After (Fixed):
- User enters address
- Bot shows "🔢 Черга відключення: 3.1" (or actual queue number)
- If it fails, shows specific error like:
  - "⚠️ Причина: Street not found in DTEK database"
  - "⚠️ Причина: Building 1 not found at this address"
  - "⚠️ Причина: Timeout loading DTEK website"
- User can run `/debug` to diagnose connection issues
- Automatic retries handle transient failures

## Error Messages Users Might See

### Transient Errors (Will Retry):
- "Timeout loading DTEK website" - Network or DTEK site slow
- "Page loaded but content seems incomplete" - Possible blocking
- "No data returned from DTEK API" - API temporary issue
- "CSRF token not found on page" - Page structure changed or blocking

### Permanent Errors (Won't Retry):
- "Street not found in DTEK database" - Street name not in database
- "Building 1 not found at this address" - Building doesn't exist at that street
- "No queue information available for this building" - Queue data missing

### System Errors:
- "Failed to launch browser: ..." - Playwright not installed correctly
- "Unknown region: ..." - Invalid region key

## Troubleshooting

### If queue detection still fails:

1. **Check Playwright is installed:**
   ```bash
   playwright install chromium
   ```

2. **Run the `/debug` command in Telegram**
   This will tell you which step is failing

3. **Check server logs:**
   ```bash
   docker-compose logs -f bot
   ```
   Look for lines with "queue_checker" for detailed diagnostics

4. **Verify the address exists on DTEK website:**
   Go to https://www.dtek-krem.com.ua/ua/shutdowns and manually enter the address

## Technical Details

### Retry Logic Flow:
```
Attempt 1 → Fail → Wait 2s → Attempt 2 → Fail → Wait 4s → Attempt 3 → Fail → Return error
         ↓ Success                     ↓ Success                     ↓ Success
         Return queue                  Return queue                  Return queue
```

### Error Classification:
- **Retryable:** Network errors, timeouts, suspect HTML, API errors
- **Non-retryable:** Street not found, building not found, no queue data (marked with `"no_retry": True`)

### User-Agent Impact:
The User-Agent mimics Chrome 128 on Windows 10. This is the same User-Agent used by the reference implementation (`Baskerville42/outage-data-ua`) which successfully scrapes DTEK sites.

Without this User-Agent, DTEK's WAF may:
- Block the request entirely (403 Forbidden)
- Return a captcha page
- Return empty/minimal content

### Wait Strategy Impact:
- `wait_until="load"`: Page HTML loaded, but JavaScript may still be running
- `wait_until="networkidle"`: All network requests completed, JavaScript finished

DTEK's website heavily relies on JavaScript to:
1. Generate CSRF tokens
2. Handle form submissions
3. Make AJAX calls to their API

Using "networkidle" ensures all of this is ready before we try to interact with the page.

## Summary

The bot should now:
1. ✅ Successfully detect queue numbers (with User-Agent and proper wait strategy)
2. ✅ Retry on transient failures (up to 3 times with backoff)
3. ✅ Show users WHY detection failed (not just "невідомо")
4. ✅ Provide `/debug` command for diagnostics
5. ✅ Accept addresses without prefixes (validates properly)

The main functionality required by the problem statement has been implemented. The `queue_from_github.py` module is a stub for future enhancement but is not critical for the core queue detection feature.
