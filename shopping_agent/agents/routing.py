import logging
from typing import Any, TypedDict

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph

from shopping_agent.agents.store_factory import StoreAgentFactory

logger = logging.getLogger(__name__)


from typing import Any, Annotated, TypedDict
from langgraph.graph.message import add_messages

# ...

class RouterState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    files: dict
    todos: list
    store: str


def _normalize_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
        return "".join(parts)
    return str(content)


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or message.get("type") or "")
    return str(getattr(message, "role", None) or getattr(message, "type", "") or "")


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        return _normalize_content(message.get("content"))
    return _normalize_content(getattr(message, "content", ""))


def _last_user_message(messages: list) -> str:
    for message in reversed(messages):
        role = _message_role(message).lower()
        if role in {"user", "human"}:
            return _message_content(message)
    if messages:
        return _message_content(messages[-1])
    return ""


def _select_messages(state: RouterState) -> dict:
    return {"messages": state.get("messages", [])}


def create_store_router_graph(
    store_agents: dict[str, Any],
    default_store: str = "general",
    checkpointer: Any = None,
):
    if not store_agents:
        raise ValueError("store_agents must not be empty")

    if default_store not in store_agents:
        default_store = next(iter(store_agents.keys()))

    async def route(state: RouterState) -> dict:
        messages = state.get("messages", [])
        user_message = _last_user_message(messages)
        logger.info(f"[Router] Routing request - user_message: {user_message[:100]}...")
        if not user_message:
            logger.info(f"[Router] No user message, using default store: {default_store}")
            return {"store": default_store}
        try:
            # ✨ 개선: 마지막 메시지만 보내는 대신 전체 메시지 기록을 보내 문맥 파악 가능하게 함
            store = await StoreAgentFactory.detect_store_via_llm(messages)
            logger.info(f"[Router] LLM detected store: {store}")
        except Exception as e:
            logger.error(f"[Router] Error detecting store: {e}")
            store = default_store
        if store not in store_agents:
            logger.warning(f"[Router] Store '{store}' not in agents, using default: {default_store}")
            store = default_store
        return {"store": store}

    def select_store(state: RouterState) -> str:
        store = state.get("store", default_store)
        selected = store if store in store_agents else default_store
        logger.debug(f"[Router] Selected store: {selected}")
        return selected

    graph = StateGraph(RouterState)
    graph.add_node("route", route)

    for store_name, agent in store_agents.items():
        graph.add_node(
            store_name,
            RunnableLambda(_select_messages) | agent,
        )
        graph.add_edge(store_name, END)

    graph.add_conditional_edges(
        "route",
        select_store,
        {name: name for name in store_agents},
    )
    graph.set_entry_point("route")
    return graph.compile(checkpointer=checkpointer)
