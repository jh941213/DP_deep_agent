from __future__ import annotations


def patch_google_genai_response_json() -> None:
    """Patch google.genai HttpResponse.json to handle non-list response_stream."""
    try:
        from google.genai._api_client import HttpResponse
    except Exception:
        return

    def _safe_json(self):  # type: ignore[no-untyped-def]
        response_stream = getattr(self, "response_stream", None)
        if isinstance(response_stream, list):
            if not response_stream or not response_stream[0]:
                return ""
            return self._load_json_from_response(response_stream[0])
        if response_stream is None:
            return ""
        try:
            return self._load_json_from_response(response_stream)
        except Exception:
            return ""

    try:
        HttpResponse.json = property(_safe_json)  # type: ignore[assignment]
    except Exception:
        return


def patch_langchain_google_genai_input() -> None:
    """Patch langchain_google_genai to force non-empty content for messages."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import BaseMessage
    except ImportError:
        return

    original_generate = ChatGoogleGenerativeAI._generate

    def _safe_generate(self, messages: list[BaseMessage], **kwargs):
        # 메시지 컨텐츠가 비어있으면 공백으로 대체하여 API 에러 방지
        for msg in messages:
            if isinstance(msg.content, str) and not msg.content:
                msg.content = " "  # Empty string -> space
            elif msg.content is None:
                msg.content = " "  # None -> space
            elif isinstance(msg.content, list) and not msg.content:
                msg.content = " "  # Empty list -> space
        
        return original_generate(self, messages, **kwargs)

    ChatGoogleGenerativeAI._generate = _safe_generate

