from __future__ import annotations

import json
import logging
import traceback

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

import asyncio

from ag_ui.core import CustomEvent, EventType, RunAgentInput, RunErrorEvent, RunFinishedEvent, RunStartedEvent
from ag_ui_langgraph.agent import LangGraphAgent, dump_json_safe
from ag_ui_langgraph.types import LangGraphEventTypes, State
from ag_ui_langgraph.utils import agui_messages_to_langchain, get_stream_payload_input, camel_to_snake
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0  # seconds, will exponentially back off


def _is_retryable_error(exc: Exception) -> bool:
    """Check if the exception is a retryable server error (5xx)."""
    error_str = str(exc).lower()
    if "500" in error_str or "internal" in error_str:
        return True
    if "502" in error_str or "503" in error_str or "504" in error_str:
        return True
    if "server" in error_str and "error" in error_str:
        return True
    if "timeout" in error_str or "timed out" in error_str:
        return True
    return False


class SafeLangGraphAgent(LangGraphAgent):
    """Disable regenerate logic to avoid missing message-id failures. Includes retry logic for 5xx errors."""

    async def run(self, input: RunAgentInput):
        logger.info(f"[{self.name}] Starting run - thread_id: {input.thread_id}, run_id: {input.run_id}")
        forwarded_props = {}
        if hasattr(input, "forwarded_props") and input.forwarded_props:
            forwarded_props = {camel_to_snake(k): v for k, v in input.forwarded_props.items()}

        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                async for event in self._handle_stream_events(input.copy(update={"forwarded_props": forwarded_props})):
                    yield event
                logger.info(f"[{self.name}] Run completed successfully - thread_id: {input.thread_id}")
                return  # Success, exit
            except Exception as exc:
                last_exc = exc
                if _is_retryable_error(exc) and attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY_BASE * (2 ** attempt)
                    logger.warning(f"[{self.name}] Retryable error (attempt {attempt + 1}/{MAX_RETRIES}): {exc}")
                    logger.info(f"[{self.name}] Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Non-retryable or max retries reached
                    logger.error(f"[{self.name}] Run failed with error: {exc}")
                    logger.error(f"[{self.name}] Traceback: {traceback.format_exc()}")
                    break

        # All retries exhausted or non-retryable error
        yield self._dispatch_event(
            RunErrorEvent(type=EventType.RUN_ERROR, message=str(last_exc))
        )
        yield self._dispatch_event(
            RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=input.thread_id,
                run_id=input.run_id,
            )
        )
        return

    async def prepare_stream(self, input: RunAgentInput, agent_state: State, config: RunnableConfig):
        state_input = input.state or {}
        messages = input.messages or []
        forwarded_props = input.forwarded_props or {}
        thread_id = input.thread_id

        state_input["messages"] = agent_state.values.get("messages", [])
        self.active_run["current_graph_state"] = agent_state.values.copy()
        langchain_messages = agui_messages_to_langchain(messages)
        state = self.langgraph_default_merge_state(state_input, langchain_messages, input)
        self.active_run["current_graph_state"].update(state)
        config["configurable"]["thread_id"] = thread_id
        interrupts = agent_state.tasks[0].interrupts if agent_state.tasks and len(agent_state.tasks) > 0 else []
        has_active_interrupts = len(interrupts) > 0
        resume_input = forwarded_props.get("command", {}).get("resume", None)

        self.active_run["schema_keys"] = self.get_schema_keys(config)

        events_to_dispatch = []
        if has_active_interrupts and not resume_input:
            events_to_dispatch.append(
                RunStartedEvent(type=EventType.RUN_STARTED, thread_id=thread_id, run_id=self.active_run["id"])
            )

            for interrupt in interrupts:
                events_to_dispatch.append(
                    CustomEvent(
                        type=EventType.CUSTOM,
                        name=LangGraphEventTypes.OnInterrupt.value,
                        value=dump_json_safe(interrupt.value),
                        raw_event=interrupt,
                    )
                )

            events_to_dispatch.append(
                RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread_id, run_id=self.active_run["id"])
            )
            return {
                "stream": None,
                "state": None,
                "config": None,
                "events_to_dispatch": events_to_dispatch,
            }

        if self.active_run["mode"] == "continue":
            await self.graph.aupdate_state(config, state, as_node=self.active_run.get("node_name"))

        if resume_input:
            if isinstance(resume_input, str):
                try:
                    resume_input = json.loads(resume_input)
                except json.JSONDecodeError:
                    pass
            stream_input = Command(resume=resume_input)
        else:
            payload_input = get_stream_payload_input(
                mode=self.active_run["mode"],
                state=state,
                schema_keys=self.active_run["schema_keys"],
            )
            stream_input = {**forwarded_props, **payload_input} if payload_input else None

        subgraphs_stream_enabled = input.forwarded_props.get("stream_subgraphs") if input.forwarded_props else False

        kwargs = self.get_stream_kwargs(
            input=stream_input,
            config=config,
            subgraphs=bool(subgraphs_stream_enabled),
            version="v2",
        )

        stream = self.graph.astream_events(**kwargs)

        return {
            "stream": stream,
            "state": state,
            "config": config,
        }
