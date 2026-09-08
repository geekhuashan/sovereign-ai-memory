from __future__ import annotations

import re


SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL), "[REDACTED PRIVATE KEY]"),
    (re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}\b"), "[REDACTED API KEY]"),
    (re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}\b"), "[REDACTED GITHUB TOKEN]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}={0,2}"), "Bearer [REDACTED]"),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|token|"
            r"client[_-]?secret|password)\s*[:=]\s*[^\s,;]{6,}"
        ),
        r"\1=[REDACTED]",
    ),
]


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
