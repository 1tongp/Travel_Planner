from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional, Literal, Dict, Any

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from .tools.utils import weatherapi_forecast, serpapi_search_maps, serpapi_search_flights, serpapi_search_hotels

# ---------------- System prompt (matches your screenshot) ----------------

SYSTEM_PROMPT = (
    "You are a travel agent. Given a destination and travel start/end date, "
    "generate a daily itinerary. For each day, use the weather_check tool to get the weather. "
    "If real weather is not available, use your general knowledge. "
    "Include activities, packing tips, and a short checklist."
)

# ---------------- Tools ----------------

@tool
def weather_check(location: str, date: str) -> str:
    """Get the weather for a location and date (YYYY-MM-DD). Uses real API if possible, else generic info."""
    data = weatherapi_forecast(location, date)
    if not data:
        return f"No real weather data for {location} on {date}. Typical weather: mild, partly cloudy."
    return (
        f"{location} on {date}: {data['condition']}, {data.get('avgtemp_c')}°C "
        f"(min {data.get('mintemp_c')}°C, max {data.get('maxtemp_c')}°C)"
    )

@tool
def find_attractions(location: str, keywords: str = "") -> str:
    """Return top attractions in a city via SerpAPI (falls back to generic suggestions)."""
    items = serpapi_search_maps(f"best attractions in {location} {keywords}".strip())
    if not items:
        return (
            "Top attractions (generic): Central Market, City Museum, Riverfront Walk, Botanical Garden, Old Town Square, "
            "Modern Art Gallery."        )
    lines = ["Top attractions:"]
    for it in items:
        piece = f"- {it.get('title')}"
        if it.get('rating'):
            piece += f" (rating {it['rating']})"
        if it.get('address'):
            piece += f" — {it['address']}"
        lines.append(piece)
    return "\n".join(lines)

@tool
def find_restaurants(location: str, style: str = "") -> str:
    """Return notable restaurants in a city via SerpAPI (falls back to generic suggestions)."""
    q = f"best {style} restaurants in {location}".strip()
    items = serpapi_search_maps(q)
    if not items:
        return (
            "Restaurant picks (generic): Kitchen & Co, Riverside Bistro, Green Leaf, Night Market Stalls, "
            "Sourdough Bakery & Cafe."        )
    lines = ["Restaurant picks:"]
    for it in items:
        piece = f"- {it.get('title')}"
        if it.get('rating'):
            piece += f" (rating {it['rating']})"
        if it.get('address'):
            piece += f" — {it['address']}"
        lines.append(piece)
    return "\n".join(lines)

@tool
def find_flights_and_hotels(origin: str, destination: str, start_date: str, end_date: str) -> str:
    """Quick helper to fetch a few flight & hotel options via SerpAPI. Fallbacks provided."""
    currency = os.environ.get("CURRENCY", "USD")
    flights = serpapi_search_flights(origin, destination, start_date, currency)
    hotels = serpapi_search_hotels(destination, start_date, end_date, currency)
    lines = [f"**Quick Options — {origin} → {destination}**"]
    if flights:
        lines.append("Flights:")
        for f in flights[:3]:
            price = f.get("price")
            price_str = f" ~{currency} {price}" if price else ""
            lines.append(f"- {f.get('title')}{price_str}")  # link omitted for brevity in LLM context
    else:
        lines.append("Flights: try Qantas, Jetstar, or Google Flights for latest prices.")
    if hotels:
        lines.append("Hotels:")
        for h in hotels[:3]:
            price = h.get("price")
            price_str = f" from {currency} {price}" if price else ""
            lines.append(f"- {h.get('title')}{price_str}: {h.get('details')}")
    else:
        lines.append("Hotels: try Booking.com or Google Hotels for availability and deals.")
    return "\n".join(lines)

TOOLS = [weather_check, find_attractions, find_restaurants, find_flights_and_hotels]

def init_chat_model(temperature: float = 0.1):
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Provide it in your .env or shell.")
    return ChatOpenAI(model_name=model_name, api_key=api_key, temperature=temperature)

def build_agent(temperature: float = 0.1):
    model = init_chat_model(temperature=temperature)
    agent = create_react_agent(model=model, tools=TOOLS, prompt=SYSTEM_PROMPT)
    return agent

# --------------- CLI smoke test ---------------

if __name__ == "__main__":
    agent = build_agent(temperature=0.0)
    user_msg = (
        "I want to travel to Melbourne from 2025-07-03 to 2025-07-05. "
        "I'm into coffee, gardens, and art. Please plan my trip."
    )
    origin = os.environ.get("DEFAULT_DEPARTURE_CITY", "Sydney")
    res = agent.invoke({"messages": [("user", user_msg)]})
    # 'res' may be an AIMessage or dict depending on version; handle both
    content = getattr(res, "content", None) or res
    print("\n--- Agent Output ---\n")
    print(content)
