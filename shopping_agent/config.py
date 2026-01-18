from typing import Optional
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()


class ShippingAddress(BaseModel):
    """배대지 주소 (미국 면세주)"""
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "US"

    def to_dict(self) -> dict:
        return {
            "street": self.street,
            "city": self.city,
            "state": self.state,
            "zip": self.zip_code,
            "country": self.country
        }


# 기본 배대지 주소 (델라웨어 - 세금 면제 주)
DEFAULT_SHIPPING_ADDRESS = ShippingAddress(
    street="123 Shipping Lane",
    city="Wilmington",
    state="DE",
    zip_code="19801"
)

class UCPConfig(BaseModel):
    """UCP 설정"""
    # Monos는 실제 UCP 지원이 확인된 상점입니다.
    store_base_url: str = "https://monos.com"
    ucp_manifest_path: str = "/.well-known/ucp"

    # 타임아웃 설정
    request_timeout: int = 30
    session_timeout: int = 3600  # 1시간

    @property
    def manifest_url(self) -> str:
        return f"{self.store_base_url}{self.ucp_manifest_path}"


class AgentConfig(BaseModel):
    """에이전트 설정"""
    # LLM 설정 - Gemini 3 Flash (최신 모델)
    model_name: str = Field(
        default="gemini-3-flash-preview",
        description="Gemini 3 Flash - 빠른 응답과 고급 추론 지원"
    )
    temperature: float = 0.1
    max_tokens: int = 4096
    request_timeout: int = Field(
        default=45,
        description="LLM 요청 타임아웃(초)"
    )

    # 재시도 설정
    max_retries: int = 3
    retry_delay: float = 1.0

    # 사용자 승인 필요 금액 (USD)
    approval_threshold: float = 100.0


class Config(BaseModel):
    """전체 설정"""
    ucp: UCPConfig = Field(default_factory=UCPConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    shipping: ShippingAddress = Field(default_factory=lambda: DEFAULT_SHIPPING_ADDRESS)

    # API 키들 (환경 변수에서 로드)
    google_api_key: Optional[str] = None
    exim_auth_key: Optional[str] = None
    ucp_auth_token: Optional[str] = None
    ucp_auth_header: str = "Authorization"
    ucp_auth_scheme: str = "Bearer"

    @classmethod
    def from_env(cls) -> "Config":
        """환경 변수에서 설정 로드"""
        return cls(
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            exim_auth_key=os.getenv("EXIM_AUTH_KEY") or os.getenv("KOREAEXIM_AUTH_KEY") or os.getenv("EXCHANGE_RATE_API_KEY"),
            ucp_auth_token=os.getenv("UCP_AUTH_TOKEN"),
            ucp_auth_header=os.getenv("UCP_AUTH_HEADER", "Authorization"),
            ucp_auth_scheme=os.getenv("UCP_AUTH_SCHEME", "Bearer"),
        )

    model_config = {"extra": "allow"}


# 기본 설정 인스턴스
config = Config.from_env()
