# Travel Agent (Streamlit + LangGraph)

A minimal but capable **Travel Planner Agent** built with **Streamlit** for the UI and **LangGraph** for the agent loop.  
It generates **daily itineraries**, **packing tips & checklist**, and can optionally look up **weather**, **attractions & restaurants**, and **flights/hotels** via API tools.

> Built to mirror the screenshots you provided: uses `create_react_agent`, a weather tool (real API with graceful fallback), plus optional SerpAPI tools.


## Features
- **Personalized itinerary** across your trip dates (energy level, interests, budget).
- **Packing tips & short checklist** (adapts to expected weather).
- **Attractions & Restaurants** lookups (SerpAPI Google Maps) — optional.
- **Weather Forecast** (WeatherAPI.com) with graceful fallback if no key.
- **Flight & Hotel** quick lookup (SerpAPI) — optional.
- Easy Streamlit UI, one command to run.

---

## Option 1 — Using `venv` (recommended)

```bash
# 1) Create and activate a virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Set environment variables via .env (recommended)
cp .env.example .env
# then edit .env to add your keys

# 4) Run the Streamlit app
streamlit run src/travel_assistant.py
```

> You can also run a quick CLI smoke test (no Streamlit):  
> `python src/agents/agent_react.py`

---

## Environment Variables

Create a `.env` at the repo root (or export in your shell).

```
# Required for LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Optional but recommended
WEATHER_API_KEY=your_weatherapi_key   # weatherapi.com
SERPAPI_API_KEY=your_serpapi_key      # serpapi.com
DEFAULT_DEPARTURE_CITY=Melbourne      # for flights helper (optional)
CURRENCY=AUD                           # for flights/hotels price display (optional)
```

All tools **gracefully fall back** to generic suggestions if a key is missing or an API call fails.

---

## Project Structure

```
travel_agent/
├─ .env.example
├─ .gitignore
├─ README.md
├─ requirements.txt
└─ src/
   ├─ travel_assistant.py        # Streamlit UI（支持 REAct / StateGraph 切换）
   └─ agents/
      ├─ __init__.py
      ├─ agent.py                # 自定义 StateGraph Agent（MemorySaver/工具调用/降噪裁剪）
      ├─ agent_react.py          # 预置 create_react_agent 版本
      └─ tools/
         ├─ __init__.py
         ├─ flights_finder.py    # 航班查询（SerpAPI，含回退）
         ├─ hotels_finder.py     # 酒店查询（SerpAPI，含回退）
         ├─ weather_check.py     # 天气（WeatherAPI，含回退）
         └─ utils.py             # 公共工具封装、截断/限流等
```

---

## Notes
- The agent is created with **`langgraph.prebuilt.create_react_agent`** bound to a set of tools (`weather_check`, `find_attractions`, `find_restaurants`, `find_flights_and_hotels`).  
- The **system prompt** mirrors your screenshot and nudges the LLM to use the tools and return clear, structured Markdown for each day.
- If your dates are in the far future (beyond forecast horizon), the weather tool switches to a **typical weather hint** and the agent still produces a great plan.
