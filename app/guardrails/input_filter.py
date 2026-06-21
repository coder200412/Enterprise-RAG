"""
Input filter guardrail — detects prompt injection and access escalation attempts.
"""
import re
from dataclasses import dataclass, field


@dataclass
class InputCheckResult:
    blocked: bool = False
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", "Prompt injection attempt detected"),
    (r"disregard\s+(all\s+)?(previous|prior|above)", "Prompt injection attempt detected"),
    (r"forget\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|rules?|context)", "Prompt injection attempt detected"),
    (r"you\s+are\s+now\s+(?:a|an)\s+", "Role manipulation attempt detected"),
    (r"pretend\s+(you\s+are|to\s+be)", "Role manipulation attempt detected"),
    (r"act\s+as\s+(if\s+you\s+are|an?\s+)", "Role manipulation attempt detected"),
    (r"new\s+instructions?\s*:", "Instruction override attempt detected"),
    (r"system\s*:\s*", "System prompt injection attempt detected"),
    (r"\[system\]", "System prompt injection attempt detected"),
    (r"<\s*system\s*>", "System prompt injection attempt detected"),
]

# Patterns that indicate RBAC escalation attempts
ESCALATION_PATTERNS = [
    (r"(show|display|reveal|give)\s+(me\s+)?all\s+documents?\s+(regardless|irrespective|without)", "Access escalation attempt"),
    (r"(bypass|skip|ignore|override)\s+(the\s+)?(access|security|clearance|rbac|permission)", "Access control bypass attempt"),
    (r"(change|set|elevate|upgrade)\s+(my\s+)?(role|clearance|access|permission)", "Privilege escalation attempt"),
    (r"(i\s+am|i'm)\s+(an?\s+)?(admin|administrator|manager|superuser|root)", "Role impersonation attempt"),
    (r"(show|reveal|display|tell)\s+(me\s+)?(the\s+)?(system\s+prompt|internal|instructions?|configuration)", "System info extraction attempt"),
    (r"what\s+(is|are)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?|configuration)", "System info extraction attempt"),
]

# Patterns that indicate potentially harmful queries
HARMFUL_PATTERNS = [
    (r"(how\s+to\s+)?(hack|exploit|attack|breach|penetrate)", "Potentially harmful query"),
    (r"(delete|destroy|drop|truncate)\s+(all|the|every)\s+(data|tables?|database|records?)", "Destructive intent detected"),
]


def check_input(query: str) -> InputCheckResult:
    """
    Check user input for prompt injection, escalation attempts,
    and harmful queries.

    Returns:
        InputCheckResult with blocked flag, reason, and warnings
    """
    result = InputCheckResult()
    query_lower = query.lower().strip()

    # Check for empty or too-short queries
    if len(query_lower) < 3:
        result.blocked = True
        result.reason = "Query too short. Please ask a complete question."
        return result

    # Check prompt injection patterns
    for pattern, reason in INJECTION_PATTERNS:
        if re.search(pattern, query_lower):
            result.blocked = True
            result.reason = reason
            return result

    # Check RBAC escalation patterns
    for pattern, reason in ESCALATION_PATTERNS:
        if re.search(pattern, query_lower):
            result.blocked = True
            result.reason = reason
            return result

    # Check harmful patterns (warn, don't block)
    for pattern, reason in HARMFUL_PATTERNS:
        if re.search(pattern, query_lower):
            result.warnings.append(reason)

    # Check for excessive special characters (potential encoding attacks)
    special_char_ratio = sum(1 for c in query if not c.isalnum() and not c.isspace()) / max(len(query), 1)
    if special_char_ratio > 0.4:
        result.warnings.append("High ratio of special characters detected")

    return result
