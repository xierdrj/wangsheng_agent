"""OpenAI-compatible Chat Completions 的同步 JD Parser 适配器。"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator, Mapping
from urllib.parse import urlparse, urlunparse

import httpx
from pydantic import ValidationError

from job_agent.application.contracts import JDParseRequest, ParsedJD
from job_agent.application.ports import JDParser, JDParserError
from job_agent.config import ConfigurationError, Settings
from job_agent.infrastructure.llm.prompts import (
    PROMPT_ID,
    PROMPT_VERSION,
    build_messages,
)
from job_agent.infrastructure.llm.schemas import JDParserModelOutput

MAX_INPUT_CHARS = 30_000
MAX_RESPONSE_BYTES = 1_048_576
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (0.5, 1.0)
RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}
TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0)


class JDParserConfigurationError(JDParserError):
    """真实 Parser 未显式启用或配置不完整。"""


class JDParserClosedError(JDParserError):
    """Parser 已关闭。"""


class JDParserInputTooLongError(JDParserError):
    """原始 JD 超过输入上限。"""


class JDParserInvalidResponseError(JDParserError):
    """Provider 返回的 envelope、JSON 或语义结构无效。"""


class JDParserProviderError(JDParserError):
    """Provider 返回不可重试的 HTTP 错误。"""


class JDParserResponseTooLargeError(JDParserError):
    """Provider 解压后响应超过上限。"""


class JDParserRetriesExhaustedError(JDParserError):
    """可重试 Provider 错误达到最大尝试次数。"""


def _endpoint(base_url: str) -> str:
    """追加 Chat Completions 路径，保留调用方显式设置的代理前缀。"""

    try:
        parsed = urlparse(base_url)
        hostname = parsed.hostname
    except ValueError as exc:
        raise JDParserConfigurationError("LLM_BASE_URL 配置无效") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise JDParserConfigurationError("LLM_BASE_URL 配置无效")
    path = parsed.path.rstrip("/")
    if "//" in path or "chat/completions" in path.casefold():
        raise JDParserConfigurationError("LLM_BASE_URL 必须是合法 API 根地址")
    return urlunparse(parsed._replace(path=f"{path}/chat/completions"))


class OpenAICompatibleJDParser:
    """使用显式配置的单一 OpenAI-compatible Provider 解析 JD。"""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None
        self._transport = transport
        self._sleeper = sleeper
        self._logger = logger or logging.getLogger(__name__)
        self._closed = False
        self._url: str | None = None
        self._configuration_error: str | None = None
        try:
            if settings.llm_provider != "openai_compatible":
                raise JDParserConfigurationError("LLM_PROVIDER 必须为 openai_compatible")
            self._url = _endpoint(settings.llm_base_url or "")
            if not settings.llm_api_key:
                raise JDParserConfigurationError("LLM_API_KEY 配置缺失")
            if not settings.llm_model or settings.llm_model.casefold() == "unset":
                raise JDParserConfigurationError("LLM_MODEL 配置缺失")
        except (JDParserConfigurationError, ConfigurationError) as exc:
            self._configuration_error = str(exc)

    def __enter__(self) -> "OpenAICompatibleJDParser":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        """幂等关闭自有 Client；不关闭调用方注入的 Client。"""

        if self._closed:
            return
        self._closed = True
        if self._owns_client and self._client is not None:
            self._client.close()

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(transport=self._transport, timeout=TIMEOUT)
        return self._client

    @staticmethod
    def _read_bounded(response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise JDParserResponseTooLargeError("LLM 响应超过 1 MiB 上限")
            chunks.append(chunk)
        return b"".join(chunks)

    def _request_body(self, raw_jd: str) -> dict[str, object]:
        schema = JDParserModelOutput.model_json_schema()
        return {
            "model": self._settings.llm_model,
            "messages": build_messages(raw_jd),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "jd_parser_v1", "strict": True, "schema": schema},
            },
        }

    def _send_once(self, request: JDParseRequest) -> tuple[bytes, int]:
        client = self._get_client()
        with client.stream(
            "POST",
            self._url,
            headers={
                "Authorization": f"Bearer {self._settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json=self._request_body(request.raw_jd),
            timeout=TIMEOUT,
        ) as response:
            status = response.status_code
            if status < 200 or status >= 300:
                return b"", status
            return self._read_bounded(response), status

    def _parse_response(self, payload: bytes, request: JDParseRequest) -> ParsedJD:
        try:
            envelope = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JDParserInvalidResponseError("LLM 响应不是有效 JSON") from exc
        if not isinstance(envelope, dict):
            raise JDParserInvalidResponseError("LLM 响应结构无效")
        choices = envelope.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise JDParserInvalidResponseError("LLM 响应 choices 数量无效")
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
            raise JDParserInvalidResponseError("LLM 响应未正常结束")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise JDParserInvalidResponseError("LLM 响应 message 无效")
        refusal = message.get("refusal")
        if refusal is not None and refusal != "":
            raise JDParserInvalidResponseError("LLM 拒绝处理该请求")
        if message.get("tool_calls"):
            raise JDParserInvalidResponseError("LLM 响应包含不支持的工具调用")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise JDParserInvalidResponseError("LLM 响应 content 为空或无效")
        try:
            semantic = JDParserModelOutput.model_validate_json(content)
            return ParsedJD.model_validate(
                {
                    **semantic.model_dump(),
                    "raw_jd": request.raw_jd,
                    "source_url": request.source_url,
                    "source_name": request.source_name,
                    "external_job_id": request.external_job_id,
                }
            )
        except ValidationError as exc:
            raise JDParserInvalidResponseError("LLM 输出未通过 Schema 校验") from exc

    def parse(self, request: JDParseRequest) -> ParsedJD:
        if not isinstance(request, JDParseRequest):
            raise TypeError("JDParser.parse 需要已校验的 JDParseRequest")
        if self._closed:
            raise JDParserClosedError("JD Parser 已关闭")
        if not self._settings.llm_enabled:
            raise JDParserConfigurationError("LLM_ENABLED 未显式启用")
        if self._configuration_error:
            raise JDParserConfigurationError(self._configuration_error)
        if len(request.raw_jd) > MAX_INPUT_CHARS:
            raise JDParserInputTooLongError("JD 原文超过 30000 字符上限")

        trace_id = (request.trace_id or "")[:128]
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1:
                self._sleeper(BACKOFF_SECONDS[attempt - 2])
            started = time.monotonic()
            try:
                payload, status = self._send_once(request)
            except httpx.TimeoutException as exc:
                safe_error = JDParserProviderError("LLM 请求超时")
                retryable = True
                status = 0
                cause: BaseException = JDParserProviderError("LLM 请求超时")
                cause.__cause__ = exc
            except httpx.NetworkError as exc:
                safe_error = JDParserProviderError("LLM 网络请求失败")
                retryable = True
                status = 0
                cause = JDParserProviderError("LLM 网络请求失败")
                cause.__cause__ = exc
            except JDParserResponseTooLargeError:
                self._logger.warning(
                    "jd_parser_failed", extra={"trace_id": trace_id, "error_code": "response_too_large"}
                )
                raise
            else:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                if status < 200 or status >= 300:
                    safe_error = JDParserProviderError("LLM Provider 返回 HTTP 错误")
                    retryable = status in RETRY_STATUS_CODES
                    cause = JDParserProviderError("LLM Provider 返回 HTTP 错误")
                else:
                    result = self._parse_response(payload, request)
                    self._logger.info(
                        "jd_parser_succeeded",
                        extra={
                            "trace_id": trace_id,
                            "prompt_id": PROMPT_ID,
                            "prompt_version": PROMPT_VERSION,
                            "provider": "openai_compatible",
                            "model": self._settings.llm_model[:128],
                            "attempt": attempt,
                            "latency_ms": elapsed_ms,
                        },
                    )
                    return result

            self._logger.warning(
                "jd_parser_attempt_failed",
                extra={
                    "trace_id": trace_id,
                    "provider": "openai_compatible",
                    "attempt": attempt,
                    "status_class": f"{status // 100}xx" if status else "network",
                    "error_code": "provider_error",
                },
            )
            if not retryable:
                raise safe_error from cause
            if attempt == MAX_ATTEMPTS:
                raise JDParserRetriesExhaustedError("LLM 请求重试次数已耗尽") from cause


__all__ = [
    "JDParserClosedError",
    "JDParserConfigurationError",
    "JDParserInputTooLongError",
    "JDParserInvalidResponseError",
    "JDParserProviderError",
    "JDParserResponseTooLargeError",
    "JDParserRetriesExhaustedError",
    "OpenAICompatibleJDParser",
]
