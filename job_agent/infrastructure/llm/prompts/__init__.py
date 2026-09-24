"""版本化 LLM Prompt。"""

from job_agent.infrastructure.llm.prompts.jd_parser_v1 import (
    PROMPT_ID,
    PROMPT_VERSION,
    build_messages,
    system_prompt,
)

__all__ = ["PROMPT_ID", "PROMPT_VERSION", "build_messages", "system_prompt"]
