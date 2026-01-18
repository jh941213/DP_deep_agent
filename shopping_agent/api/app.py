"""
에이전트 서버

에이전트 이벤트를 실시간 스트리밍
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from langgraph.checkpoint.memory import MemorySaver

from shopping_agent.api.langgraph_agent import SafeLangGraphAgent
from shopping_agent.patches.google_genai import patch_google_genai_response_json, patch_langchain_google_genai_input
from shopping_agent.agents import (
    STORE_URLS,
    create_store_agent,
    create_store_router_graph,
)

patch_google_genai_response_json()
patch_langchain_google_genai_input()

app = FastAPI(title="직구 에이전트 서버")
AGENT_CONFIG = {"recursion_limit": 200}

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store_graphs = {
    name: create_store_agent(name).with_config(AGENT_CONFIG)
    for name in STORE_URLS.keys()
}
store_agents = {
    name: SafeLangGraphAgent(
        name=name,
        description=f"{name} 스토어 에이전트",
        graph=graph,
        config=AGENT_CONFIG,
    )
    for name, graph in store_graphs.items()
}

# 자동 라우팅 엔드포인트
router_graph = create_store_router_graph(store_graphs, checkpointer=MemorySaver()).with_config(AGENT_CONFIG)
router_agent = SafeLangGraphAgent(
    name="router",
    description="상점 자동 라우팅",
    graph=router_graph,
    config=AGENT_CONFIG,
)
add_langgraph_fastapi_endpoint(app, router_agent, "/agent")

# 상점별 고정 엔드포인트 (디버그/직접 호출용)
for store_name, agent in store_agents.items():
    add_langgraph_fastapi_endpoint(app, agent, f"/agent/{store_name}")


@app.get("/")
async def root():
    return {
        "message": "직구 에이전트 서버",
        "endpoints": ["/agent"] + [f"/agent/{name}" for name in STORE_URLS.keys()],
        "docs": "/docs"
    }


@app.get("/stores")
async def list_stores():
    return {"stores": list(STORE_URLS.keys())}


# --- Wallet Payment API ---
from pydantic import BaseModel
from typing import Dict, Any
import json
from shopping_agent.tools.ucp import _ucp_complete_checkout

class PaymentRequest(BaseModel):
    store_url: str
    checkout_id: str
    payment_token: Dict[str, Any]

@app.post("/api/pay")
async def process_payment(request: PaymentRequest):
    """
    Zero-Click Payment Endpoint:
    프론트엔드에서 결제 토큰을 받아 UCP complete_checkout을 직접 호출합니다.
    """
    # 1. Pydantic 모델에서 dict 및 JSON 변환
    payment_json_str = json.dumps(request.payment_token)
    
    # 2. 내부 로직 함수 직접 호출 (도구 우회)
    result_json = _ucp_complete_checkout(
        store_url=request.store_url,
        checkout_id=request.checkout_id,
        payment_json=payment_json_str
    )
    
    # 3. 결과 반환
    try:
        return json.loads(result_json)
    except Exception:
        return {"raw_result": result_json}


__all__ = ["app"]
