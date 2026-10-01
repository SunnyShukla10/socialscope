from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Mapping, Sequence

from app.config import settings
from app.platforms import PLATFORM_PROVIDERS

PLATFORM_NAMES = {
    "twitter": "Twitter / X",
    "x": "Twitter / X",
    "instagram": "Instagram",
    "reddit": "Reddit",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "facebook": "Facebook",
    "pinterest": "Pinterest",
}

PROVIDER_NAMES = {
    "xpoz": "Xpoz",
    "socialvault": "SociaVault",
    "unknown": "Unknown provider",
}


@dataclass(frozen=True)
class QueryValidationIssue:
    code: str
    platform: str
    provider: str
    actual_length: int
    maximum_length: int
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


class QueryValidationError(ValueError):
    def __init__(self, issue: QueryValidationIssue):
        super().__init__(issue.message)
        self.issue = issue


def configured_provider_limits() -> dict[str, int]:
    return {
        "xpoz": settings.XPOZ_QUERY_MAX_LENGTH,
        "socialvault": settings.SOCIALVAULT_QUERY_MAX_LENGTH,
    }


def _platform_context(
    platform: str,
    provider_limits: Mapping[str, int],
    safe_default: int,
) -> tuple[str, str, int]:
    normalized = platform.strip().lower()
    provider = PLATFORM_PROVIDERS.get(normalized, "unknown")
    return normalized, provider, provider_limits.get(provider, safe_default)


def _message(
    code: str,
    platform: str,
    provider: str,
    actual_length: int,
    maximum_length: int,
) -> str:
    platform_name = PLATFORM_NAMES.get(platform, platform.title() or "Selected platform")
    provider_name = PROVIDER_NAMES.get(provider, provider.title())
    if code == "QUERY_TOO_LONG":
        return (
            f"{platform_name} via {provider_name} is configured for queries up to "
            f"{maximum_length} characters; this query has {actual_length}. "
            "Shorten the query without changing its intended meaning."
        )
    if code == "UNBALANCED_PARENTHESES":
        return f"The query has unbalanced parentheses for {platform_name} via {provider_name}."
    if code == "UNBALANCED_QUOTES":
        return f'The query has an unbalanced double quote for {platform_name} via {provider_name}.'
    if code == "UNSUPPORTED_BOOLEAN_OPERATOR":
        return (
            f"{platform_name} via {provider_name} does not accept && or || here. "
            "Use the words AND or OR."
        )
    return f"The Boolean query is malformed for {platform_name} via {provider_name}."


def _syntax_error_code(query: str) -> str | None:
    if not query.strip():
        return "MALFORMED_BOOLEAN_QUERY"
    in_quote = False
    escaped = False
    depth = 0
    outside_quotes: list[str] = []

    for character in query:
        if escaped:
            escaped = False
            if not in_quote:
                outside_quotes.append(character)
            continue
        if character == "\\":
            escaped = True
            if not in_quote:
                outside_quotes.append(character)
            continue
        if character == '"':
            in_quote = not in_quote
            outside_quotes.append(" ")
            continue
        if in_quote:
            outside_quotes.append(" ")
            continue

        outside_quotes.append(character)
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return "UNBALANCED_PARENTHESES"

    if in_quote:
        return "UNBALANCED_QUOTES"
    if depth:
        return "UNBALANCED_PARENTHESES"

    boolean_text = "".join(outside_quotes)
    if "&&" in boolean_text or "||" in boolean_text:
        return "UNSUPPORTED_BOOLEAN_OPERATOR"
    if re.match(r"^\s*(?:AND|OR)\b", boolean_text):
        return "MALFORMED_BOOLEAN_QUERY"
    if re.search(r"\b(?:AND|OR|NOT)\s*$", boolean_text):
        return "MALFORMED_BOOLEAN_QUERY"
    if re.search(r"\b(?:AND|OR)\s+(?:AND|OR)\b", boolean_text):
        return "MALFORMED_BOOLEAN_QUERY"
    if re.search(r"\bNOT\s+(?:AND|OR)\b", boolean_text):
        return "MALFORMED_BOOLEAN_QUERY"
    if re.search(r"\(\s*\)", boolean_text):
        return "MALFORMED_BOOLEAN_QUERY"
    return None


def validate_query(
    query: str,
    platforms: Sequence[str],
    *,
    provider_limits: Mapping[str, int] | None = None,
    safe_default: int | None = None,
) -> None:
    limits = dict(provider_limits or configured_provider_limits())
    default_limit = safe_default or settings.QUERY_SAFE_DEFAULT_MAX_LENGTH
    contexts = [_platform_context(platform, limits, default_limit) for platform in platforms]
    if not contexts:
        contexts = [("", "unknown", default_limit)]

    actual_length = len(query)
    exceeded = [context for context in contexts if actual_length > context[2]]
    if exceeded:
        platform, provider, maximum_length = min(exceeded, key=lambda item: item[2])
        code = "QUERY_TOO_LONG"
        raise QueryValidationError(
            QueryValidationIssue(
                code=code,
                platform=platform,
                provider=provider,
                actual_length=actual_length,
                maximum_length=maximum_length,
                message=_message(code, platform, provider, actual_length, maximum_length),
            )
        )

    syntax_code = _syntax_error_code(query)
    if syntax_code:
        platform, provider, maximum_length = contexts[0]
        raise QueryValidationError(
            QueryValidationIssue(
                code=syntax_code,
                platform=platform,
                provider=provider,
                actual_length=actual_length,
                maximum_length=maximum_length,
                message=_message(
                    syntax_code,
                    platform,
                    provider,
                    actual_length,
                    maximum_length,
                ),
            )
        )


def query_limits_payload() -> dict:
    provider_limits = configured_provider_limits()
    platforms = {}
    for platform, provider in PLATFORM_PROVIDERS.items():
        if platform == "x":
            continue
        platforms[platform] = {
            "provider": provider,
            "maximum_length": provider_limits.get(
                provider,
                settings.QUERY_SAFE_DEFAULT_MAX_LENGTH,
            ),
        }
    return {
        "safe_default_maximum_length": settings.QUERY_SAFE_DEFAULT_MAX_LENGTH,
        "warning_ratio": settings.QUERY_LENGTH_WARNING_RATIO,
        "limits_are_official_provider_guarantees": False,
        "providers": {
            provider: {"maximum_length": maximum_length}
            for provider, maximum_length in provider_limits.items()
        },
        "platforms": platforms,
    }
