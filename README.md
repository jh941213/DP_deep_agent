# 직구 에이전트 (Direct Purchase Agent)

**직구 에이전트(DPAGENT)**는 사용자의 쇼핑 의도를 파악하여 Kith, Monos, Everlane, Allbirds 등 해외 유명 쇼핑몰에서 상품을 검색하고, 재고를 확인하며, **Google UCP(Universal Commerce Protocol)**를 통해 결제까지 지원하는 프리미엄 AI 에이전트 서비스입니다.

![App Screenshot](frontend/public/cart.png)

## 🚀 주요 기능 (Core Features)

### 1. 인텔리전트 멀티턴 라우팅 (Intelligent Multi-turn Routing)
- **맥락 인식**: 단순 키워드 매칭이 아닌, **LLM 기반 라우터**가 사용자의 대화 흐름을 깊이 있게 분석합니다.
- **멀티턴 지원**: "그거 재고 있어?"와 같은 대명사가 포함된 후속 질문도 이전 대화 기록(History)을 참조하여 정확한 상점 에이전트(예: Kith Agent)로 연결합니다.

### 2. Universal Commerce Protocol (UCP) 통합
- **표준화된 결제**: 쇼핑몰마다 상이한 결제 프로세스를 UCP 표준으로 통일하여 사용자에게 일관된 결제 경험을 제공합니다.
- **핵심 로직**:
  - `ucp_create_checkout`: 장바구니 생성 및 체크아웃 세션 활성화.
  - `build_line_item_from_handle`: 상품 핸들을 UCP 규격의 라인 아이템으로 정규화.
  - (주의: 해당 상점의 `/.well-known/ucp.json` 지원 여부에 따라 최적화되어 동작합니다.)

### 3. 고신뢰성 백엔드 및 자동 복구 (Robustness)
- **자동 재시도(Retry)**: Google Gemini API의 일시적 장애(500/503) 시 지수 백오프(Exponential Backoff) 전략으로 자동 재시도하여 중단 없는 서비스를 제공합니다.
- **안정성 패치**: API 호출 시 발생할 수 있는 데이터 누락이나 빈 메시지 에러를 방지하기 위해 `patches/google_genai.py`를 통한 입출력 정규화 패치가 적용되어 있습니다.

### 4. 프리미엄 UI/UX
- **Glassmorphism Design**: 투명도와 블러 효과를 활용한 모던하고 고급스러운 인터페이스를 제공합니다.
- **실시간 사고 과정 시각화**: 에이전트가 어떤 도구를 호출하고, 어떤 할 일(Todo)을 수행 중인지 실시간 배지 및 로그로 시각화합니다.

---

## 🏗️ 아키텍처 (Architecture)

```mermaid
graph TD
    User[User] -->|Message| Frontend[Next.js Client]
    Frontend -->|API Request| Backend[FastAPI Server]
    
    subgraph Backend System
        Router[Router Agent] -->|Context & Intent Analysis| StoreSelector{Store Selection}
        StoreSelector -->|Kith| KithAgent[Kith Agent]
        StoreSelector -->|Monos| MonosAgent[Monos Agent]
        StoreSelector -->|General| GeneralAgent[General Agent]
        
        KithAgent & MonosAgent -->|Function Calls| Tools[Tools Layer]
        
        Tools -->|Search/Stock| StoreAPI[Store Website]
        Tools -->|Checkout| UCP[UCP Handler]
    end
    
    UCP -->|Order| UCP_Endpoint[Store UCP Endpoint]
```

1. **Frontend**: React, TailwindCSS, Framer Motion 기반의 고반응성 대화형 웹 인터페이스.
2. **Router**: `shopping_agent/agents/routing.py`에서 전체 대화 맥락을 분석해 최적의 전문 에이전트를 선별.
3. **Store Agents**: `LangGraph` 기반으로 동작하며, 각 상점에 최적화된 시스템 프롬프트와 도구 셋을 보유.
4. **Tools Layer**: 환율 연동, 관세 계산기, 실시간 재고 조회 등 실질적인 쇼핑 보조 기능을 수행.

---

## 🧠 Deep Agent 아키텍처 (Deep Agent Technology)

본 프로젝트의 정체성은 단순한 챗봇이 아닌, **자율적으로 추론하고 문제를 해결하는 'Deep Agent'**에 있습니다.

### 1. 자율적 추론 및 계획 (Reasoning & Planning)
- **TodoListMiddleware**: 작업을 시작하기 전 스스로 할 일 목록을 작성하고, 수행 결과에 따라 동적으로 계획을 수정합니다.
- **Thinking Block**: 모델의 내부 판단 과정을 UI에 분리하여 노출함으로써 사용자에게 에이전트의 논리적 흐름을 투명하게 전달합니다.

### 2. 미들웨어 확장 구조 (Middleware Pattern)
- **`ShoppingToolsMiddleware`**: 검색, 재고 확인, 관세 계산 등 복잡한 비즈니스 로직을 에이전트의 사고 루프에 유기적으로 결합합니다.
- 독립적인 미들웨어 구조로 설계되어 새로운 쇼핑몰이나 기능을 코드 수정 최소화로 추가할 수 있습니다.

### 3. 지능형 메모리 시스템 (Persistent State)
- **`CompositeBackend`**: 세션 기반의 실시간 상태(`StateBackend`)와 파일 시스템 기반의 장기 기억(`FilesystemBackend`)을 통합 관리합니다.
- `.memories/` 디렉토리를 통해 사용자의 과거 요청 스타일이나 특이사항을 학습하고 참조합니다.

---

## 🏁 시작하기 (Getting Started)

### 1. 필수 요구사항
- Python 3.11+
- Node.js 18+
- `uv` 패키지 매니저 (권장)

### 2. 환경 변수 설정
루트 디렉토리에 `.env` 파일을 생성하고 아래 키를 입력하세요.

```env
GOOGLE_API_KEY=your_gemini_api_key
EXIM_AUTH_KEY=your_exim_api_key
```

### 3. 실행 방법
제공된 통합 실행 스크립트를 통해 백엔드와 프론트엔드를 동시에 구동할 수 있습니다.

```bash
chmod +x run.sh
./run.sh
```
- **Backend API**: http://localhost:8000
- **Frontend App**: http://localhost:3001

---

## 💱 환율 및 금융 데이터 (Financial Data)

정확한 직구 가격 산출을 위해 **한국수출입은행(Korea Eximbank) Open API**를 활용합니다.

- **실시간 고시 환율**: 대한민국 원화(KRW) 기준 유효 환율을 실시간으로 가져옵니다.
- **스마트 캐싱**: `shopping_agent/.cache/exchange_rates.json`을 통해 불필요한 API 호출을 방지하고 빠른 응답 속도를 보장합니다.
- **관세/부가세 자동 계산**: 품목별 관세율과 환율을 결합하여 최종 납부 금액을 추정합니다.

---

## 🔒 UCP 인증 및 보안 (UCP & Security)

일부 브랜드(Monos, Kith 등)의 UCP API는 엄격한 보안을 유지합니다. 에이전트는 이를 스마트하게 극복합니다.

### 자동 폴백(Fallback) 시스템
1. UCP API 호출 시 인증 에러(`AuthenticationFailed`)가 발생하면 시스템이 이를 즉시 감지합니다.
2. 에러를 출력하는 대신, 내부적으로 **Shopify Cart Permalink** 시스템을 가동하여 유효한 다이렉트 결제 주소를 생성합니다.
3. 사용자는 중단 없이 "결제하기" 버튼을 통해 실제 쇼핑몰의 카트로 연결됩니다.

---

## 🐛 트러블슈팅 (Troubleshooting)

**Q. Gemini API 호출 중 `ValueError: contents are required`가 발생합니다.**
- **A**: 해당 이슈는 빈 메시지가 모델에 전달될 때 발생합니다. 현재 `patches/google_genai.py`를 통해 모든 빈 스트링을 자동으로 안전하게 처리하고 있으므로, 최신 소스 코드를 확인해 주세요.

---

**Coded with ❤️ by @jh941213**
