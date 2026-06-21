"""
Output filter guardrail — scrubs PII and sensitive data from LLM responses.
"""
import re
from dataclasses import dataclass, field


@dataclass
class OutputFilterResult:
    filtered_text: str = ""
    flags: list[str] = field(default_factory=list)
    redactions: int = 0


# PII patterns with replacement labels
PII_PATTERNS = [
    # Email addresses
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL REDACTED]", "Email address detected and redacted"),
    # Phone numbers (various formats)
    (r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE REDACTED]", "Phone number detected and redacted"),
    # SSN (US format)
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN REDACTED]", "Social Security Number detected and redacted"),
    # Credit card numbers
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "[CARD REDACTED]", "Credit card number detected and redacted"),
    # Database connection strings
    (r"\b[a-zA-Z0-9\+]+://[^:\s]+:[^@\s]+@[^\s]+", "[DB CONNECTION REDACTED]", "Database connection string detected and redacted"),
    # Codenames
    (r"(?i)\bProject\s+(?:Mercury|Apollo|Orion|Nova|Falcon|Alpha|Beta)\b", "[CODENAME REDACTED]", "Internal project codename detected and redacted"),
    # Local server IP addresses
    (r"\b(?:127\.\d{1,3}\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})\b", "[LOCAL IP REDACTED]", "Local server IP address detected and redacted"),
    # IP addresses
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP REDACTED]", "IP address detected and redacted"),
]

# Patterns that suggest the LLM leaked internal information
LEAKAGE_PATTERNS = [
    (r"clearance[\s_]?level\s*[:=]\s*\d", "clearance_level metadata leaked"),
    (r"(system\s+prompt|internal\s+instructions?)\s*:", "System prompt leaked"),
    (r"doc_id\s*[:=]\s*\d", "Internal document ID leaked"),
    (r"role_id\s*[:=]\s*\d", "Internal role ID leaked"),
    (r"hashed_password", "Password hash leaked"),
    (r"jwt[\s_]?(secret|token|key)", "JWT secret leaked"),
]


def filter_output(text: str) -> OutputFilterResult:
    """
    Scrub PII and sensitive data from LLM output.

    Returns:
        OutputFilterResult with filtered text, flags, and redaction count
    """
    result = OutputFilterResult(filtered_text=text)

    # Apply PII redactions
    for pattern, replacement, flag in PII_PATTERNS:
        matches = re.findall(pattern, result.filtered_text)
        if matches:
            result.filtered_text = re.sub(pattern, replacement, result.filtered_text)
            result.flags.append(flag)
            result.redactions += len(matches)

    # Check for internal data leakage
    for pattern, flag in LEAKAGE_PATTERNS:
        if re.search(pattern, result.filtered_text, re.IGNORECASE):
            result.flags.append(flag)
            # Remove the leaked metadata
            result.filtered_text = re.sub(
                pattern, "[REDACTED]", result.filtered_text, flags=re.IGNORECASE
            )
            result.redactions += 1

    return result
