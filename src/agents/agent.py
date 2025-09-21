from __future__ import annotations

import os, datetime, operator, json
from uuid import uuid4
from typing import Annotated, TypedDict, List, Any, Dict

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from langchain_openai import ChatOpenAI
from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_core.tools import Tool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.tools.flights_finder import flights_finder
from agents.tools.hotels_finder import hotels_finder
from agents.tools.weather_check import weather_check
from langchain_core.messages.utils import trim_messages

MAX_TOKENS_CTX = 6000  # 让输入侧(不是输出)控制在 ~6k tokens 以内

def _prune_messages(msgs: list, llm) -> list:
    # 保证 tool 对齐的逻辑可以先做一遍（见你现有函数）
    base = msgs  # 如果你已有 ensure-pair 的逻辑，这里用处理后的结果

    # 再用 token 级别裁剪
    trimmed = trim_messages(
        base,
        # LangChain 0.2+ 的 OpenAI 模型都支持这个计数器
        token_counter=llm,         # 传 self._tools_llm 也可以
        max_tokens=MAX_TOKENS_CTX,
        strategy="last",           # 保留最近
    )
    return trimmed

CURRENT_YEAR = datetime.datetime.now().year

class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]

TOOLS_SYSTEM_PROMPT = f"""
You are a smart travel agency. Use the tools to look up information.
You are allowed to make multiple calls (either together or in sequence).
Only look up information when you are sure of what you want.
The current year is {{CURRENT_YEAR}}.

If you need to look up some information before asking a follow up question, you are allowed to do that.
In your output include links to hotels websites and flights websites (if possible).
In your output always include the price of the flight and the price of the hotel and the currency as well (if possible).
For example for hotels:
Rate: $181 per night
Total: $3,488
""".replace("{CURRENT_YEAR}", str(CURRENT_YEAR))

TOOLS: List[Tool] = [flights_finder, hotels_finder, weather_check]

class ToolExecutionError(Exception): pass
class AgentError(Exception): pass

def _get_openai_key() -> str | None:
    # Try Streamlit secrets first (if running in Streamlit), then env
    try:
        import streamlit as st
        v = st.secrets.get("OPENAI_API_KEY", None)
        if v:
            return v
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY")

class Agent:
    def __init__(self, temperature: float = 0.1):
        self._tools: Dict[str, Tool] = {t.name: t for t in TOOLS}
        self._tools_llm = ChatOpenAI(
            model_name=os.environ.get("OPENAI_MODEL","gpt-4o-mini"),
            api_key=os.environ.get("OPENAI_API_KEY"),
            temperature=temperature
        ).bind_tools(TOOLS)

        builder = StateGraph(AgentState)
        builder.add_node("call_tools_llm", self.call_tools_llm)
        builder.add_node("invoke_tools", self.invoke_tools)
        builder.set_entry_point("call_tools_llm")
        builder.add_conditional_edges("call_tools_llm", Agent.exists_action, {"more_tools":"invoke_tools","done":END})
        builder.add_edge("invoke_tools", "call_tools_llm")
        self.graph = builder.compile(checkpointer=MemorySaver())

        self._error_count = 0
        self._max_retries = 3

    @staticmethod
    def exists_action(state: AgentState) -> str:
        result = state["messages"][-1]
        if hasattr(result, "tool_calls") and len(result.tool_calls) > 0:
            return "more_tools"
        return "done"

    # def call_tools_llm(self, state: AgentState) -> AgentState:
    #     messages = state["messages"]
    #     messages = [SystemMessage(content=TOOLS_SYSTEM_PROMPT)] + messages
    #     msg = self._tools_llm.invoke(messages)
    #     return {"messages": messages + [msg]}
    def call_tools_llm(self, state: AgentState) -> AgentState:
        original = state["messages"]
        pruned = _prune_messages(original, self._tools_llm)
        messages = [SystemMessage(content=TOOLS_SYSTEM_PROMPT)] + pruned
        msg = self._tools_llm.invoke(messages)
        # 关键：把新 assistant 追加到原始 state（不要把带 System 的 messages 写回去）
        return {"messages": state["messages"] + [msg]}


    def invoke_tools(self, state: AgentState) -> AgentState:
        tool_calls = state["messages"][-1].tool_calls
        results: List[AnyMessage] = []
        failed_tools: List[str] = []

        for tool_call in tool_calls:
            tool_name = tool_call["name"] if "name" in tool_call else tool_call["function"]["name"]
            tool_id = tool_call.get("id") or tool_call["id"]
            args = tool_call.get("args") or tool_call["function"].get("arguments", {})
            if isinstance(args, str):
                try: args = json.loads(args)
                except Exception: args = {}

            try:
                if tool_name not in self._tools:
                    raise ToolExecutionError(f"Tool '{tool_name}' not found")
                result = self._tools[tool_name].invoke(args)

                # Normalize obvious error payloads into readable messages
                if isinstance(result, dict) and "error" in result:
                    failed_tools.append(tool_name)
                    error_msg = self._format_error_message(tool_name, result["error"])
                    result = error_msg

                results.append(ToolMessage(tool_call_id=tool_id, name=tool_name, content=str(result)))

            except Exception as e:
                failed_tools.append(tool_name)
                error_msg = self._format_error_message(tool_name, str(e))
                results.append(ToolMessage(tool_call_id=tool_id, name=tool_name, content=error_msg))

        # If we have failed tools, increment error count
        if failed_tools:
            self._error_count += 1

        # If exceeded retries, force completion by generating a fallback plan
        if self._error_count >= self._max_retries and failed_tools:
            final_message = self._generate_fallback_plan(state["messages"][0].content, failed_tools)
            return {"messages": [final_message]}

        return {"messages": results}

    def _format_error_message(self, tool_name: str, err: str) -> str:
        return f"[{tool_name.upper()} ERROR] {err}. The assistant will continue with available information."

    def _generate_fallback_plan(self, original_prompt: str, failed_tools: list) -> AnyMessage:
        fallback_prompt = f"""Generate a fallback plan when tools fail.
The following tools failed: {', '.join(failed_tools)}.
Original request: {original_prompt}

Please generate a travel plan using only the information we have available.
Focus on providing:
1. A general daily itinerary
2. Local attractions and restaurant recommendations
3. General packing tips
4. A basic travel checklist

Clearly indicate which information is missing and provide alternative suggestions where possible.
"""
        messages = [
            SystemMessage(content=TOOLS_SYSTEM_PROMPT + " If tools are unavailable, give a best-effort plan."),
            ("user", fallback_prompt),
        ]
        ans = self._tools_llm.invoke(messages)
        return ans

    # convenience method
    def run(self, user_prompt: str, thread_id: str | None = None) -> str:
        tid = thread_id or str(uuid4())
        result = self.graph.invoke({"messages":[("user", user_prompt)]}, config={"configurable": {"thread_id": tid}})
        msgs = result["messages"]
        # Try to find final AI content
        for m in reversed(msgs):
            if getattr(m,"type",None) in ("ai","assistant"):
                return getattr(m,"content","")
        return str(result)
