from __future__ import annotations

import os
import json
import requests
from typing import List, Dict, Any, Optional

def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name, default)
    return v if v not in ("", None) else None

# ---------------- WeatherAPI helper ----------------

def weatherapi_forecast(location: str, date: str) -> Optional[Dict[str, Any]]:
    """
    Returns a dict with minimal normalized fields using WeatherAPI.com if key exists.
    On error or missing key, returns None.
    """
    api_key = _get_env("WEATHER_API_KEY")
    if not api_key:
        return None
    try:
        # WeatherAPI: forecast.json can accept future dates with 'days',
        # but we'll try with 'dt' first (as in your screenshot) and gracefully fallback.
        url = "https://api.weatherapi.com/v1/forecast.json"
        params = {
            "key": api_key,
            "q": location,
            "dt": date,
            "aqi": "no",
            "alerts": "no",
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            # Fallback: fetch at least 1 day forecast window
            params2 = {"key": api_key, "q": location, "days": 1, "aqi": "no", "alerts": "no"}
            resp2 = requests.get(url, params=params2, timeout=10)
            resp2.raise_for_status()
            data = resp2.json()
        else:
            data = resp.json()

        f = data.get("forecast", {})
        days = f.get("forecastday", [])
        if not days:
            return None
        day = days[0].get("day", {})
        condition = day.get("condition", {}).get("text", "N/A")
        return {
            "condition": condition,
            "avgtemp_c": day.get("avgtemp_c"),
            "mintemp_c": day.get("mintemp_c"),
            "maxtemp_c": day.get("maxtemp_c"),
        }
    except Exception:
        return None

# ---------------- SerpAPI helpers ----------------

def serpapi_search_maps(query: str, type_filter: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Uses SerpAPI google_maps engine to fetch places.
    Returns list of dicts: {title, rating, address, link}
    """
    api_key = _get_env("SERPAPI_API_KEY")
    if not api_key:
        return []
    try:
        from serpapi import GoogleSearch
        params = {
            "engine": "google_maps",
            "type": "search",
            "q": query,
            "api_key": api_key,
        }
        if type_filter:
            params["ll"] = "@"  # no-op; maps engine doesn't use 'type' directly like Places API
        search = GoogleSearch(params)
        results = search.get_dict()
        locals_ = results.get("local_results", []) or results.get("place_results", []) or []
        out = []
        for r in locals_[:limit]:
            out.append({
                "title": r.get("title") or r.get("name"),
                "rating": r.get("rating"),
                "address": r.get("address"),
                "link": r.get("link") or r.get("place_id"),
            })
        return out
    except Exception:
        return []

def serpapi_search_flights(origin: str, destination: str, date: str, currency: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Very light wrapper using SerpAPI. If google_flights fails, fall back to generic web search results.
    Returns list of dicts with {title, price, details, link}.
    """
    api_key = _get_env("SERPAPI_API_KEY")
    if not api_key:
        return []
    try:
        from serpapi import GoogleSearch
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": date,
            "currency": currency or _get_env("CURRENCY") or "USD",
            "api_key": api_key,
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        flights = results.get("best_flights") or results.get("other_flights") or []
        out = []
        for f in flights[:5]:
            price = f.get("price")
            link = results.get("search_metadata", {}).get("google_flights_url")
            summary = f.get("summary") or f.get("airline") or "Flight option"
            out.append({"title": summary, "price": price, "details": f.get("itinerary") or f, "link": link})
        if out:
            return out
        # fallback to normal search if no structured results
        params2 = {
            "engine": "google",
            "q": f"flights from {origin} to {destination} on {date}",
            "api_key": api_key,
        }
        results2 = GoogleSearch(params2).get_dict()
        organic = results2.get("organic_results", [])
        out2 = []
        for r in organic[:5]:
            out2.append({"title": r.get("title"), "price": None, "details": r.get("snippet"), "link": r.get("link")})
        return out2
    except Exception:
        return []

def serpapi_search_hotels(location: str, check_in: str, check_out: str, currency: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Very light wrapper using SerpAPI. If google_hotels fails, fall back to generic web search.
    Returns list of dicts {title, price, details, link}.
    """
    api_key = _get_env("SERPAPI_API_KEY")
    if not api_key:
        return []
    try:
        from serpapi import GoogleSearch
        params = {
            "engine": "google_hotels",
            "q": f"hotels in {location}",
            "check_in_date": check_in,
            "check_out_date": check_out,
            "currency": currency or _get_env("CURRENCY") or "USD",
            "api_key": api_key,
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        hotels = results.get("properties", [])
        out = []
        for h in hotels[:5]:
            out.append({"title": h.get("name"), "price": h.get("rate_per_night", {}).get("lowest"), 
                        "details": h.get("address"), "link": h.get("link")})
        if out:
            return out
        # fallback
        params2 = {
            "engine": "google",
            "q": f"best hotels in {location} {check_in} to {check_out}",
            "api_key": api_key,
        }
        results2 = GoogleSearch(params2).get_dict()
        organic = results2.get("organic_results", [])
        out2 = []
        for r in organic[:5]:
            out2.append({"title": r.get("title"), "price": None, "details": r.get("snippet"), "link": r.get("link")})
        return out2
    except Exception:
        return []
