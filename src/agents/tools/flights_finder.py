from __future__ import annotations
import logging, os
from langchain_core.tools import tool
from .utils import serpapi_search_flights

logger = logging.getLogger(__name__)

@tool
def flights_finder(origin: str, destination: str, date: str, currency: str | None = None) -> dict:
    """
    Find a few flight options using SerpAPI. Returns a dict with structured items for the agent.
    """
    currency = currency or os.environ.get("CURRENCY","USD")
    logger.info("agents.tools.flights_finder: ✈ Searching flights with parameters: origin=%s, destination=%s, date=%s, currency=%s",
                origin, destination, date, currency)
    items = serpapi_search_flights(origin, destination, date, currency)
    if not items:
        return {"items": [], "note": "No structured flight results. Try airline sites or Google Flights."}
    return {"currency": currency, "items": items}
