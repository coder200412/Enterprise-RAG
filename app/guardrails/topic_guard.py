"""
Topic guard — rejects queries that are clearly off-topic
for a corporate document assistant.
"""
import re
from dataclasses import dataclass


@dataclass
class TopicCheckResult:
    blocked: bool = False
    reason: str = ""


# Off-topic query patterns
OFF_TOPIC_PATTERNS = [
    (r"(write|generate|create)\s+(me\s+)?(a\s+)?(poem|song|story|essay|joke|code|script|program)", 
     "I'm a corporate document assistant. I can only answer questions about company documents."),
    (r"(what'?s?\s+the\s+weather|weather\s+forecast|temperature\s+in)", 
     "I can only answer questions about company documents, not weather."),
    (r"(tell\s+me\s+a\s+joke|make\s+me\s+laugh|something\s+funny)", 
     "I'm a corporate document assistant and cannot tell jokes. Please ask about company documents."),
    (r"(who\s+will\s+win|sports?\s+score|game\s+result|betting)", 
     "I can only answer questions about company documents, not sports or betting."),
    (r"(recipe\s+for|how\s+to\s+cook|cooking\s+instructions?)", 
     "I can only answer questions about company documents, not cooking recipes."),
    (r"(personal\s+advice|relationship|dating|love\s+life)", 
     "I'm a corporate document assistant and cannot provide personal advice."),
    (r"(translate\s+.+\s+to|translation\s+of)", 
     "I'm a document assistant, not a translation service. Please ask about company documents."),
]

# Keywords that strongly indicate corporate/document queries (allow-list)
CORPORATE_KEYWORDS = [
    "document", "report", "policy", "procedure", "financial", "revenue",
    "budget", "meeting", "minutes", "quarter", "annual", "employee",
    "handbook", "guideline", "compliance", "regulation", "department",
    "project", "plan", "strategy", "performance", "review", "contract",
    "agreement", "memo", "announcement", "update", "summary", "analysis",
    "data", "metric", "kpi", "target", "goal", "objective", "deadline",
    "company", "organization", "corporate", "board", "executive",
    "salary", "benefit", "leave", "attendance", "training",
]


def check_topic(query: str) -> TopicCheckResult:
    """
    Check if a query is on-topic for a corporate document assistant.

    Returns:
        TopicCheckResult with blocked flag and reason
    """
    query_lower = query.lower().strip()

    # Check explicit off-topic patterns
    for pattern, reason in OFF_TOPIC_PATTERNS:
        if re.search(pattern, query_lower):
            return TopicCheckResult(blocked=True, reason=reason)

    # If the query contains corporate keywords, it's likely on-topic
    for keyword in CORPORATE_KEYWORDS:
        if keyword in query_lower:
            return TopicCheckResult(blocked=False)

    # For ambiguous queries, allow them through (the RAG pipeline will
    # naturally return "no relevant documents" if nothing matches)
    return TopicCheckResult(blocked=False)
