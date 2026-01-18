from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver

from shopping_agent.config import config
from shopping_agent.agents.stores import STORE_PROMPTS
from shopping_agent.tools import ShoppingToolsMiddleware


def _memories_dir() -> Path:
    root_dir = Path(__file__).resolve().parents[1]
    memories_dir = root_dir / ".memories"
    memories_dir.mkdir(parents=True, exist_ok=True)
    return memories_dir


def _build_backend():
    memories_dir = _memories_dir()
    return lambda rt: CompositeBackend(
        default=StateBackend(rt),
        routes={
            "/memories/": FilesystemBackend(
                root_dir=str(memories_dir),
                virtual_mode=True,
            ),
        },
    )


def create_store_agent(store_name: str):
    """
    상점별 Deep Agent 생성 (미들웨어 패턴 적용)

    Args:
        store_name: 상점 이름 (monos, everlane, allbirds, kith)

    Returns:
        DeepAgent 인스턴스
    """
    store_key = store_name.lower()

    if store_key not in STORE_PROMPTS:
        raise ValueError(f"지원하지 않는 상점: {store_name}")

    # Gemini 모델 초기화
    model = init_chat_model(
        model=config.agent.model_name,
        model_provider="google_genai",
        api_key=config.google_api_key,
        temperature=config.agent.temperature,
        retries=config.agent.max_retries,
        request_timeout=config.agent.request_timeout,
    )

    return create_deep_agent(
        model=model,
        system_prompt=STORE_PROMPTS[store_key],
        middleware=[
            # TodoListMiddleware는 create_deep_agent에 기본 포함됨
            ShoppingToolsMiddleware(),      # 쇼핑 도구 (search, stock, exchange, customs)
        ],
        backend=_build_backend(),
        checkpointer=MemorySaver(),
    )

