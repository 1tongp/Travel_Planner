from __future__ import annotations
import logging, os
from langchain_core.tools import tool
from .utils import serpapi_search_hotels

logger = logging.getLogger(__name__)

@tool
def hotels_finder(location: str, check_in: str, check_out: str, currency: str | None = None, adults: int = 1, children: int = 0, rooms: int = 1, sort_by: str | None = None, hotel_class: str | None = None) -> dict:
    """
    Find a few hotel options using SerpAPI Google Hotels. Returns a dict with structured items for the agent.
    """
    currency = currency or os.environ.get("CURRENCY","USD")
    logger.info("agents.tools.hotels_finder: 🏨 Location: %s | Check-in: %s | Check-out: %s", location, check_in, check_out)
    logger.info("agents.tools.hotels_finder: 👥 Adults: %s, Children: %s, Rooms: %s | sort_by: %s, hotel_class: %s", adults, children, rooms, sort_by, hotel_class)
    items = serpapi_search_hotels(location, check_in, check_out, currency)
    if not items:
        return {"items": [], "note": "No structured hotel results. Try Booking.com or Google Hotels."}
    return {"currency": currency, "items": items}
