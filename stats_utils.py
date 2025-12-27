"""Statistics tracking utilities for print jobs."""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger("sticker_factory.stats_utils")

STATS_FILE = "print_stats.json"


def load_stats():
    """Load statistics from JSON file."""
    if not os.path.exists(STATS_FILE):
        return []
    
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading stats: {e}")
        return []


def save_stats(stats):
    """Save statistics to JSON file."""
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving stats: {e}")


def record_print(printer_name, printer_model=None):
    """Record a successful print job."""
    stats = load_stats()
    
    # Add new print record
    record = {
        "timestamp": datetime.now().isoformat(),
        "printer_name": printer_name,
        "printer_model": printer_model or "",
    }
    
    stats.append(record)
    
    # Keep only last 10000 records to prevent file from growing too large
    if len(stats) > 10000:
        stats = stats[-10000:]
    
    save_stats(stats)
    logger.debug(f"Recorded print for printer: {printer_name}")


def get_stats_by_date(printer_name=None):
    """
    Get statistics grouped by date and printer.
    
    Returns:
        dict: {date: {printer_name: count}}
    """
    stats = load_stats()
    date_stats = defaultdict(lambda: defaultdict(int))
    
    for record in stats:
        if printer_name and record.get("printer_name") != printer_name:
            continue
        
        # Parse timestamp and get date
        try:
            timestamp = datetime.fromisoformat(record["timestamp"])
            date_str = timestamp.strftime("%Y-%m-%d")
            printer = record.get("printer_name", "Unknown")
            date_stats[date_str][printer] += 1
        except Exception as e:
            logger.warning(f"Error parsing timestamp: {e}")
            continue
    
    return dict(date_stats)


def get_total_stats():
    """Get total statistics per printer."""
    stats = load_stats()
    totals = defaultdict(int)
    
    for record in stats:
        printer = record.get("printer_name", "Unknown")
        totals[printer] += 1
    
    return dict(totals)


def get_stats_summary():
    """Get summary statistics."""
    stats = load_stats()
    totals = get_total_stats()
    
    if not stats:
        return {
            "total_prints": 0,
            "printers": {},
            "first_print": None,
            "last_print": None,
        }
    
    # Get first and last print timestamps
    timestamps = [datetime.fromisoformat(r["timestamp"]) for r in stats if "timestamp" in r]
    timestamps.sort()
    
    return {
        "total_prints": len(stats),
        "printers": totals,
        "first_print": timestamps[0].isoformat() if timestamps else None,
        "last_print": timestamps[-1].isoformat() if timestamps else None,
    }


def get_prints_today():
    """Get count of prints made today (resets at midnight)."""
    stats = load_stats()
    today = datetime.now().date()
    count = 0
    
    for record in stats:
        try:
            timestamp = datetime.fromisoformat(record["timestamp"])
            if timestamp.date() == today:
                count += 1
        except Exception as e:
            logger.warning(f"Error parsing timestamp: {e}")
            continue
    
    return count


def get_prints_total():
    """Get total count of all prints."""
    stats = load_stats()
    return len(stats)

