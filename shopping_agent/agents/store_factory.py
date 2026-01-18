"""
Store Agent Factory

상점명에 따라 적절한 Deep Agent 인스턴스를 반환합니다.
"""

import json

import langchain_google_genai as google

from shopping_agent.agents.store_agent import create_store_agent
from shopping_agent.agents.stores import STORE_URLS
from shopping_agent.config import config


class StoreAgentFactory:
    """상점 에이전트 생성을 위한 팩토리 클래스"""

    @staticmethod
    def get_agent(store_name: str):
        """상점명에 해당하는 Deep Agent 반환"""
        store_key = store_name.lower()

        if store_key not in STORE_URLS:
            return None

        return create_store_agent(store_key)

    @staticmethod
    async def detect_store_via_llm(messages: list) -> str:
        """전체 대화 맥락을 기반으로 인텔리전트 라우팅 수행"""
        llm = google.ChatGoogleGenerativeAI(
            model=config.agent.model_name,
            google_api_key=config.google_api_key,
            temperature=0,
            retries=config.agent.max_retries,
            request_timeout=config.agent.request_timeout,
        )

        history_str = ""
        for i, msg in enumerate(messages[-5:]):  # 최근 5개 메시지만 문맥으로 사용
            role = "User" if (getattr(msg, "role", None) or getattr(msg, "type", "")) in ["user", "human"] else "Assistant"
            content = getattr(msg, "content", "")
            if not content and isinstance(msg, dict):
                content = msg.get("content", "")
            history_str += f"{role}: {content}\n"
        
        print(f"DEBUG: Router History Context:\n{history_str}")  # 디버깅용 로그 추가

        system_prompt = f"""사용자의 현재 요청과 대화 맥락을 분석하여 가장 적합한 상점을 하나만 선택하세요.

**중요한 규칙**:
1. 사용자가 **"구매하고 싶어", "결제해줘", "그거 살래"** 같이 구체적인 상품 명시 없이 구매 의사를 밝힌 경우, **이전 대화 맥락(History)에서 가장 최근에 논의된 상점**을 선택해야 합니다. 절대 'general'로 보내지 마세요.
2. 대화 맥락에서 이전에 언급된 상품이나 브랜드가 있다면 해당 상점을 우선적으로 선택하세요.
3. 명확한 상점 변경 의사가 없다면 기존 상점 맥락을 유지하세요.

상점 목록:
- 'monos': 캐리어, 여행용 가방, 액세서리
- 'everlane': 의류, 티셔츠, 패션
- 'allbirds': 편안한 신발, 울 슈즈
- 'kith': 나이키, 뉴발란스, 아디다스 스니커즈

현재 대화 내역:
{history_str}

만약 사용자의 요청이 단순히 인사이거나(예: "안녕"), 상점과 전혀 무관한 일반적인 잡담이거나, 이전 맥락도 없고 상점도 유추할 수 없는 경우에만 'general'을 선택하세요.

답변은 JSON 형식: {{"store": "kith"}} 또는 {{"store": "general"}}"""

        try:
            # 💡 detect_store_via_llm 자체는 히스토리에 의존하므로 human 메시지는 마지막 메시지로 전달
            last_msg = messages[-1] if messages else None
            last_query = getattr(last_msg, "content", "") if last_msg else ""
            if isinstance(last_msg, dict):
                last_query = last_msg.get("content", "")
            
            if not last_query or not str(last_query).strip():
                return "general"

            response = await llm.ainvoke(
                [("system", system_prompt), ("human", f"현재 요청: {last_query}")],
                config={"metadata": {"emit-messages": False, "emit-tool-calls": False}},
            )
            content = response.content
            if isinstance(content, list):
                content = "".join(p if isinstance(p, str) else p.get("text", "") for p in content)
            content = content.strip()
            if "{" in content and "}" in content:
                content = content[content.find("{"):content.rfind("}")+1]
            return json.loads(content).get("store", "general")
        except Exception as e:
            print(f"⚠️ LLM 라우팅 실패: {e}")
            return "general"  # 기본값
