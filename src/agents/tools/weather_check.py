from __future__ import annotations
import logging
from langchain_core.tools import tool
from .utils import weatherapi_forecast

logger = logging.getLogger(__name__)

@tool
def weather_check(location: str, date: str) -> str:
    """Get weather by location and date (YYYY-MM-DD). Real API if possible; otherwise generic fallback."""
    logger.info("weather_check:Received weather check params: location=%s date=%s", location, date)
    data = weatherapi_forecast(location, date)
    if not data:
        return f"No real weather data for {location} on {date}. Typical weather: mild, partly cloudy."
    return f"{location} on {date}: {data['condition']}, {data.get('avgtemp_c')}°C (min {data.get('mintemp_c')}°C, max {data.get('maxtemp_c')}°C)"
