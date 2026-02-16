# Changes Summary: Old vs New Implementation

## Overview

This document summarizes the complete rebuild of the DTEK bot, highlighting the critical fixes for queue detection and confirm button functionality.

## Critical Problems Fixed

### 1. Queue Number Always "невідомо"

**Old Implementation (BROKEN):**
```python
# services/queue_checker.py (old)
async def _fill_form_and_get_queue():
    # ❌ Tried to fill form using Playwright
    await _fill_autocomplete(page, "city", city)
    await _fill_autocomplete(page, "street", street)
    await _fill_autocomplete(page, "house_num", building)
    
    # ❌ Tried to read from JavaScript variable
    queue_group = await page.evaluate(
        "() => window.DisconSchedule?.group || null"
    )
    # Often returned null or undefined
```

**Problems:**
- Form filling unreliable (autocomplete timing issues)
- DisconSchedule.group often not set
- No fallback mechanism

**New Implementation (FIXED):**
```python
# services/queue_checker.py (new)
async def get_queue_number():
    # ✅ Direct AJAX request to DTEK API
    
    # 1. Get CSRF token
    csrf_token = await page.evaluate(
        "() => document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')"
    )
    
    # 2. Build form data
    form_data = {
        "method": "getHomeNum",
        "data[0][name]": "city",
        "data[0][value]": city,
        "data[1][name]": "street",
        "data[1][value]": street,
        "data[2][name]": "house_num",
        "data[2][value]": building,
        "data[3][name]": "updateFact",
        "data[3][value]": current_datetime,
    }
    
    # 3. POST to /ua/ajax
    response = await page.request.post(
        ajax_url,
        headers={"X-CSRF-TOKEN": csrf_token},
        form=form_data,
    )
    
    # 4. Parse JSON response
    response_data = await response.json()
    queue_number = response_data.get("group")
```

**Key Improvements:**
- ✅ Direct API call (no form interaction)
- ✅ Reliable CSRF token extraction
- ✅ Proper error handling
- ✅ Based on working dtek-monitor approach

### 2. Confirm Button Error

**Old Implementation (BROKEN):**
```python
# bot/handlers.py (old)
async def confirm_address_handler(update, context):
    # ❌ No validation of context.user_data
    region_key = context.user_data["region"]  # Could KeyError
    
    # ❌ Fallback logic for missing queue_number column
    try:
        await add_address(..., queue_number=queue_number)
    except Exception as insert_err:
        # Complex fallback to add_address_without_queue
        if 'queue_number' in error_msg:
            await add_address_without_queue(...)
```

**Problems:**
- Missing keys caused KeyError
- Complex error handling
- Database column issues

**New Implementation (FIXED):**
```python
# bot/handlers.py (new)
async def confirm_address_handler(update, context):
    # ✅ Validate all required keys
    required_keys = ["region", "city", "street", "building"]
    missing_keys = [k for k in required_keys if k not in context.user_data]
    
    if missing_keys:
        logger.error("Missing user_data keys: %s", missing_keys)
        await update.message.reply_text("❌ Виникла помилка...")
        context.user_data.clear()
        return ConversationHandler.END
    
    # ✅ Extract data safely
    region_key = context.user_data["region"]
    city = context.user_data["city"]
    street = context.user_data["street"]
    building = context.user_data["building"]
    queue_number = context.user_data.get("queue_number")
    
    # ✅ Handle "невідомо" case
    if queue_number == "невідомо" or not queue_number:
        queue_number = None
    
    # ✅ Save directly (no complex fallback needed)
    await add_address(
        db, user_id=db_user["id"], region=region_key,
        city=city, street=street, building=building,
        full_address=full_address,
        normalized_address=normalized,
        queue_number=queue_number,
    )
    
    # ✅ Always clear user_data
    context.user_data.clear()
```

**Key Improvements:**
- ✅ Validates context.user_data keys
- ✅ Proper error messages
- ✅ Simplified logic
- ✅ Always clears user_data

### 3. Database Schema

**Old Implementation:**
```sql
-- database/migrations/init.sql (old)
CREATE TABLE addresses (
    -- ... other columns ...
    normalized_address TEXT
    -- ❌ queue_number NOT in CREATE TABLE
);

-- ❌ Added later via ALTER TABLE (could fail)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='addresses' AND column_name='queue_number') THEN
        ALTER TABLE addresses ADD COLUMN queue_number VARCHAR(20);
    END IF;
END $$;
```

**New Implementation:**
```sql
-- database/migrations/init.sql (new)
CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    region VARCHAR(50) NOT NULL,
    city VARCHAR(255),
    street VARCHAR(255) NOT NULL,
    building VARCHAR(50),
    full_address TEXT NOT NULL,
    normalized_address TEXT,
    queue_number VARCHAR(20),  -- ✅ In main CREATE TABLE
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Improvements:**
- ✅ queue_number in main CREATE TABLE
- ✅ No complex ALTER TABLE logic
- ✅ Guaranteed to exist on fresh install

## Queue Support: 102 Queues

**Old Implementation:**
```python
# config/regions.py (old)
REGIONS = {
    "kyiv": {"name": "Київ", "code": "kem", ...},
    # ... other regions ...
}
# ❌ No explicit queue list
# ❌ No verification of total count
```

**New Implementation:**
```python
# config/regions.py (new)
# Kyiv - 66 queues
KYIV_QUEUES = [
    "1.1", "1.2", "2.1", "2.2", "3.1", "3.2",
    "4.1", "4.2", "5.1", "5.2", "6.1", "6.2",
    "7.1", "8.1", ..., "60.1",  # 54 additional
]

# Other regions - 12 queues each
KYIV_REGION_QUEUES = ["1.1", ..., "6.2"]
DNIPRO_QUEUES = ["1.1", ..., "6.2"]
ODESA_QUEUES = ["1.1", ..., "6.2"]

REGION_QUEUES = {
    "kyiv": KYIV_QUEUES,           # 66
    "kyiv_region": KYIV_REGION_QUEUES,  # 12
    "dnipro": DNIPRO_QUEUES,       # 12
    "odesa": ODESA_QUEUES,         # 12
}

# ✅ Verification
TOTAL_QUEUES = sum(len(q) for q in REGION_QUEUES.values())
assert TOTAL_QUEUES == 102, f"Expected 102, got {TOTAL_QUEUES}"
```

## Files Deleted

Removed old implementations:
- ❌ `parsers/base_parser.py`
- ❌ `parsers/kyiv_parser.py`
- ❌ `parsers/kyiv_region_parser.py`
- ❌ `parsers/dnipro_parser.py`
- ❌ `parsers/odesa_parser.py`
- ❌ `services/address_matcher.py`
- ❌ `services/notification.py`
- ❌ `utils/logger.py`
- ❌ `init_db.py`
- ❌ `railway.json`
- ❌ `nixpacks.toml`
- ❌ `Procfile`
- ❌ `.dockerignore`

## Files Created/Replaced

### New Core Files
- ✅ `config/settings.py` - Clean settings management
- ✅ `config/regions.py` - 102 queues configuration
- ✅ `services/queue_checker.py` - AJAX-based queue detection
- ✅ `services/outage_checker.py` - Unified outage checking
- ✅ `services/notifier.py` - User notifications
- ✅ `services/monitoring.py` - Periodic monitoring
- ✅ `parsers/dtek_parser.py` - Unified DTEK parser
- ✅ `bot/handlers.py` - Fixed handlers with proper validation
- ✅ `database/connection.py` - Clean connection management
- ✅ `database/models.py` - Complete CRUD operations
- ✅ `utils/helpers.py` - Utility functions

### Documentation
- ✅ `README.md` - Complete documentation
- ✅ `TESTING.md` - Testing guide
- ✅ `CHANGES.md` - This file
- ✅ `.env.example` - Environment template

### Deployment
- ✅ `Dockerfile` - Production-ready Docker image
- ✅ `docker-compose.yml` - Local development setup

## Testing Checklist

- [ ] **Queue Detection:**
  - [ ] Test with Kyiv address
  - [ ] Test with Kyiv region address
  - [ ] Test with Dnipro address
  - [ ] Test with Odesa address
  - [ ] Verify queue numbers are accurate

- [ ] **Confirm Button:**
  - [ ] Add address and click confirm
  - [ ] Verify address is saved in database
  - [ ] Verify queue_number is saved
  - [ ] Verify no error messages

- [ ] **Full Flow:**
  - [ ] /start command
  - [ ] Add address (complete flow)
  - [ ] View addresses (/my_addresses)
  - [ ] Check status (/status)
  - [ ] Delete address
  - [ ] Verify monitoring runs every 5 minutes

- [ ] **Edge Cases:**
  - [ ] Address with no queue number
  - [ ] Invalid city/street format
  - [ ] Database connection failure
  - [ ] DTEK website timeout

## Migration Path

For existing deployments:

1. **Backup Database:**
   ```bash
   pg_dump dtek_bot > backup.sql
   ```

2. **Pull New Code:**
   ```bash
   git pull origin main
   ```

3. **Update Dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Verify Database Schema:**
   ```sql
   -- Check if queue_number column exists
   SELECT column_name FROM information_schema.columns 
   WHERE table_name = 'addresses' AND column_name = 'queue_number';
   ```

5. **Restart Bot:**
   ```bash
   # Stop old bot
   docker-compose down
   
   # Start new bot
   docker-compose up -d
   ```

6. **Test Queue Detection:**
   - Add a new address
   - Verify queue number is detected
   - Check logs for "AJAX response received"

## Success Metrics

After deployment, verify:

1. ✅ Queue numbers are detected (not "невідомо")
2. ✅ Confirm button works without errors
3. ✅ All 102 queues are supported
4. ✅ Database has queue_number column
5. ✅ Bot starts without errors
6. ✅ Monitoring runs every 5 minutes
7. ✅ Notifications are sent for new outages

## Support

For issues:
1. Check logs: `docker-compose logs -f bot`
2. Review TESTING.md for debugging steps
3. Open GitHub issue with logs and description
