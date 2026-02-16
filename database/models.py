"""Database models and CRUD operations."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.connection import Database

logger = logging.getLogger("database.models")


# ==================== Users ====================

async def create_user(
    db: Database,
    chat_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update user in database.
    
    Args:
        db: Database connection
        chat_id: Telegram chat ID
        username: Telegram username
        first_name: User's first name
        last_name: User's last name
        
    Returns:
        User record as dict
    """
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            """
            INSERT INTO users (chat_id, username, first_name, last_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (chat_id) DO UPDATE 
            SET username = $2, first_name = $3, last_name = $4
            RETURNING *
            """,
            chat_id,
            username,
            first_name,
            last_name,
        )


async def get_user_by_chat_id(db: Database, chat_id: int) -> Optional[Dict[str, Any]]:
    """Get user by Telegram chat ID.
    
    Args:
        db: Database connection
        chat_id: Telegram chat ID
        
    Returns:
        User record or None
    """
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE chat_id = $1",
            chat_id,
        )


async def get_all_active_users(db: Database) -> List[Dict[str, Any]]:
    """Get all active users.
    
    Args:
        db: Database connection
        
    Returns:
        List of user records
    """
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM users WHERE is_active = TRUE"
        )


# ==================== Addresses ====================

async def add_address(
    db: Database,
    user_id: int,
    region: str,
    city: str,
    street: str,
    building: str,
    full_address: str,
    normalized_address: str,
    queue_number: Optional[str] = None,
) -> Dict[str, Any]:
    """Add new address for user.
    
    Args:
        db: Database connection
        user_id: User ID
        region: Region key
        city: City name
        street: Street name
        building: Building number
        full_address: Full address string
        normalized_address: Normalized address for matching
        queue_number: Queue number (optional)
        
    Returns:
        Address record as dict
    """
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            """
            INSERT INTO addresses (
                user_id, region, city, street, building,
                full_address, normalized_address, queue_number
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            user_id,
            region,
            city,
            street,
            building,
            full_address,
            normalized_address,
            queue_number,
        )


async def get_user_addresses(db: Database, user_id: int) -> List[Dict[str, Any]]:
    """Get all addresses for user.
    
    Args:
        db: Database connection
        user_id: User ID
        
    Returns:
        List of address records
    """
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT * FROM addresses 
            WHERE user_id = $1 
            ORDER BY created_at DESC
            """,
            user_id,
        )


async def count_user_addresses(db: Database, user_id: int) -> int:
    """Count addresses for user.
    
    Args:
        db: Database connection
        user_id: User ID
        
    Returns:
        Number of addresses
    """
    async with db.pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM addresses WHERE user_id = $1",
            user_id,
        )
        return result or 0


async def delete_address(db: Database, address_id: int, user_id: int) -> bool:
    """Delete address.
    
    Args:
        db: Database connection
        address_id: Address ID
        user_id: User ID (for security check)
        
    Returns:
        True if deleted, False otherwise
    """
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM addresses 
            WHERE id = $1 AND user_id = $2
            """,
            address_id,
            user_id,
        )
        return result == "DELETE 1"


async def update_address_queue(
    db: Database, address_id: int, queue_number: str
) -> bool:
    """Update queue number for address.
    
    Args:
        db: Database connection
        address_id: Address ID
        queue_number: New queue number
        
    Returns:
        True if updated, False otherwise
    """
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE addresses 
            SET queue_number = $1 
            WHERE id = $2
            """,
            queue_number,
            address_id,
        )
        return result == "UPDATE 1"


# ==================== Outages ====================

async def create_outage(
    db: Database,
    region: str,
    outage_type: str,
    affected_area: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    description: Optional[str] = None,
    source_url: Optional[str] = None,
    raw_data: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create new outage record.
    
    Args:
        db: Database connection
        region: Region key
        outage_type: Type of outage (emergency, planned)
        affected_area: Affected area description
        start_time: Start time
        end_time: End time
        description: Outage description
        source_url: Source URL
        raw_data: Raw data as JSON
        
    Returns:
        Outage record as dict
    """
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            """
            INSERT INTO outages (
                region, outage_type, affected_area,
                start_time, end_time, description,
                source_url, raw_data
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            region,
            outage_type,
            affected_area,
            start_time,
            end_time,
            description,
            source_url,
            raw_data,
        )


async def get_active_outages(db: Database, region: str) -> List[Dict[str, Any]]:
    """Get active outages for region.
    
    Args:
        db: Database connection
        region: Region key
        
    Returns:
        List of outage records
    """
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT * FROM outages 
            WHERE region = $1 
            AND (end_time IS NULL OR end_time > NOW())
            ORDER BY start_time DESC
            """,
            region,
        )


async def delete_old_outages(db: Database, days: int = 7) -> int:
    """Delete outages older than specified days.
    
    Args:
        db: Database connection
        days: Number of days to keep
        
    Returns:
        Number of deleted records
    """
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM outages 
            WHERE end_time < NOW() - INTERVAL '%s days'
            """,
            days,
        )
        # Extract number from "DELETE N"
        return int(result.split()[-1]) if result else 0


# ==================== Notifications ====================

async def create_notification(
    db: Database,
    user_id: int,
    outage_id: int,
) -> Optional[Dict[str, Any]]:
    """Create notification record (or skip if already exists).
    
    Args:
        db: Database connection
        user_id: User ID
        outage_id: Outage ID
        
    Returns:
        Notification record or None if already exists
    """
    try:
        async with db.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                INSERT INTO notifications (user_id, outage_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, outage_id) DO NOTHING
                RETURNING *
                """,
                user_id,
                outage_id,
            )
    except Exception as e:
        logger.error("Failed to create notification: %s", e)
        return None


async def get_user_notifications(
    db: Database, user_id: int, limit: int = 10
) -> List[Dict[str, Any]]:
    """Get recent notifications for user.
    
    Args:
        db: Database connection
        user_id: User ID
        limit: Maximum number of records
        
    Returns:
        List of notification records with outage details
    """
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT n.*, o.outage_type, o.affected_area, o.start_time, o.end_time
            FROM notifications n
            JOIN outages o ON n.outage_id = o.id
            WHERE n.user_id = $1
            ORDER BY n.sent_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
