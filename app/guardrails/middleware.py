"""
Guardrails middleware — not used as actual ASGI middleware.
Re-exports the guardrail functions for convenient import.
"""
from app.guardrails.input_filter import check_input, InputCheckResult
from app.guardrails.output_filter import filter_output, OutputFilterResult
from app.guardrails.topic_guard import check_topic, TopicCheckResult

__all__ = [
    "check_input",
    "InputCheckResult",
    "filter_output",
    "OutputFilterResult",
    "check_topic",
    "TopicCheckResult",
]
