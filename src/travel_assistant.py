from __future__ import annotations

import os
from datetime import date, timedelta
from typing import List

import streamlit as st
from dotenv import load_dotenv, find_dotenv
from uuid import uuid4
import logging

# Load environment (.env at project root)
load_dotenv(find_dotenv())
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from agents.agent_react import build_agent

st.set_page_config(page_title="Travel Planner Agent", page_icon="✈️", layout="wide")

st.title("✈️ Travel Planner Agent")

# Persist a conversation/thread id for LangGraph checkpointing
if not st.session_state.get("thread_id"):
    st.session_state["thread_id"] = str(uuid4())
st.markdown(
    "Generate a **daily itinerary**, **packing tips**, **checklist**, and optional lookups for "
    "**weather**, **attractions/restaurants**, and **flights/hotels**."
)

with st.sidebar:
    st.header("Settings")
    engine = st.radio("Agent Engine", ["StateGraph (custom)", "REAct (prebuilt)"], index=0)
    temperature = st.slider("Model Temperature", 0.0, 1.2, 0.2, 0.1)
    want_attractions = st.checkbox("Suggest Attractions", value=True)
    want_food = st.checkbox("Suggest Restaurants", value=True)
    want_flights_hotels = st.checkbox("Include Flights & Hotels (SerpAPI)", value=False)
    origin_city = st.text_input("Departure City (for flights)", os.environ.get("DEFAULT_DEPARTURE_CITY", "Melbourne"))
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    st.caption(f"Using model: `{model_name}`")

# ---- Inputs ----
col1, col2, col3 = st.columns([2,1,1])
with col1:
    destination = st.text_input("Destination City", placeholder="e.g., Melbourne", value="Melbourne")
with col2:
    start = st.date_input("Start Date", value=date.today() + timedelta(days=7))
with col3:
    end = st.date_input("End Date", value=date.today() + timedelta(days=10))

prefs = st.multiselect(
    "Interests / Preferences",
    ["coffee", "gardens", "art", "history", "shopping", "nightlife", "hikes", "beach", "kids activities", "museums", "foodie"],
    default=["coffee", "gardens", "art"]
)
energy = st.selectbox("Energy Level", ["chill", "balanced", "full-throttle"], index=1)
budget = st.select_slider("Budget", options=["shoestring", "value", "mid", "premium", "luxury"], value="mid")
notes = st.text_area("Extra Notes (optional)", placeholder="e.g., traveling with kids; prefer walkable areas; need halal options...")

go = st.button("Plan my trip 🚀")

def date_range(d1: date, d2: date) -> List[date]:
    cur = d1
    while cur <= d2:
        yield cur
        cur = cur + timedelta(days=1)

if go:
    if not destination or end < start:
        st.error("Please provide a destination and valid start/end dates.")
        st.stop()

    days = list(date_range(start, end))
    want_bits = []
    if want_attractions: want_bits.append("attractions")
    if want_food: want_bits.append("restaurants")
    if want_flights_hotels: want_bits.append("flights & hotels")

    # Build prompt
    interests = ", ".join(prefs) if prefs else "general city highlights"
    extra = f"Additional notes: {notes}" if notes else ""
    ask = (
        f"You are planning a trip to {destination} from {start} to {end}. "
        f"Traveler preferences: {interests}; energy: {energy}; budget: {budget}. {extra} "
        f"For each day, use the weather_check tool with the correct date. "
        f"Also include a short checklist and packing tips tailored to the weather and activities. "
    )
    if want_attractions:
        ask += "Use find_attractions to suggest 3-5 must-see places. "
    if want_food:
        ask += "Use find_restaurants to suggest 2-4 places to eat. "
    if want_flights_hotels:
        ask += f"At the end, call find_flights_and_hotels with origin '{origin_city}' and the trip dates. "

    with st.spinner("Thinking & planning..."):
        if engine.startswith("StateGraph"):
            from agents.agent import Agent
            agent = Agent(temperature=temperature)
            content = agent.run(ask, thread_id=st.session_state["thread_id"])
        else:
            from agents.agent_react import build_agent as _build
            agent = _build(temperature=temperature)
            res = agent.invoke({"messages": [("user", ask)]})
            content = getattr(res, "content", None) or str(res)
    st.markdown("---")
    st.subheader("Itinerary")
    st.markdown(content)

    st.download_button(
        "Download Itinerary (Markdown)",
        data=content.encode("utf-8"),
        file_name=f"itinerary_{destination}_{start}_{end}.md",
        mime="text/markdown"
    )

st.markdown("---")
st.caption("Tip: set your keys in `.env` — OPENAI_API_KEY (required), WEATHER_API_KEY & SERPAPI_API_KEY (optional).")
