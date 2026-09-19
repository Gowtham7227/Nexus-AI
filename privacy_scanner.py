import re
import json
from typing import Dict, List, Any, Tuple, Optional


# ============================================================
# PRIVACY SCANNER & PII DETECTOR
# ============================================================

class PrivacyFinding:
    def __init__(self, name: str, severity: str, matched_text: str, start: int, end: int, sample_masked: str):
        self.entity_type = name.upper().replace(" ", "_").replace("/", "_")
        self.name = name
        self.severity = severity
        self.matched_text = matched_text
        self.start = start
        self.end = end
        self.sample_masked = sample_masked

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "name": self.name,
            "severity": self.severity,
            "start": self.start,
            "end": self.end,
            "sample_masked": self.sample_masked,
        }


class PrivacyScanner:
    """
    Deterministic privacy & PII scanner.
    Detects emails, phone numbers, SSNs, credit cards, API keys, tokens,
    passwords, private keys, and classifies severity: LOW, MEDIUM, HIGH, CRITICAL.
    """

    # 1. API Keys, Tokens & Private Keys (CRITICAL)
    PATTERNS_CRITICAL = [
        ("AWS Access Key", r"\bAKIA[0-9A-Z]{16}\b", "CRITICAL"),
        ("AWS Secret Key", r"(?i)\b(?:aws_secret_access_key|aws_secret_key|secret_key)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?", "CRITICAL"),
        ("Google API Key", r"\bAIza[0-9A-Za-z\-_]{35}\b", "CRITICAL"),
        ("OpenAI API Key", r"\bsk-[A-Za-z0-9\-_]{20,}\b", "CRITICAL"),
        ("GitHub Personal Token", r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,})\b", "CRITICAL"),
        ("Slack Token", r"\bxox[baprs]-[0-9A-Za-z\-]{20,}\b", "CRITICAL"),
        ("JWT / Bearer Token", r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b", "CRITICAL"),
        ("Private Encryption Key", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----", "CRITICAL"),
        ("Password / Secret Assignment", r"(?i)\b(?:password|passwd|secret|api_key|apikey|auth_token)\s*[:=]\s*['\"]?([^\s'\"]{6,})['\"]?", "CRITICAL"),
    ]

    # 2. Financial & Government Identifiers (HIGH)
    PATTERNS_HIGH = [
        ("US SSN", r"\b\d{3}-\d{2}-\d{4}\b", "HIGH"),
        ("Indian Aadhaar", r"\b[2-9]\d{3}\s\d{4}\s\d{4}\b", "HIGH"),
        ("Indian PAN", r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", "HIGH"),
        ("Credit Card", r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b", "HIGH"),
        ("Bank Account IBAN", r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b", "HIGH"),
    ]

    # 3. Contact & Personal Identifiers (MEDIUM / LOW)
    PATTERNS_MEDIUM = [
        ("Email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "MEDIUM"),
        ("International Phone", r"\b\+(?:[0-9][-.\s]?){7,14}[0-9]\b", "MEDIUM"),
        ("US Phone", r"\b(?:\+?1[-.\s])?\(?[2-9]\d{2}\)?[-.\s]\d{3}[-.\s]\d{4}\b", "MEDIUM"),
        ("Indian Phone", r"\b(?:\+?91[-.\s]?)?[6-9]\d{4}[-.\s]?\d{5}\b", "MEDIUM"),
    ]

    PATTERNS_LOW = [
        ("Employee ID", r"\b(?:EMP|EMP_ID|STAFF)[-_]?[0-9]{4,8}\b", "LOW"),
        ("IPv4 Address", r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b", "LOW"),
    ]

    @staticmethod
    def _validate_luhn(card_number_str: str) -> bool:
        digits = [int(c) for c in card_number_str if c.isdigit()]
        if len(digits) < 13 or len(digits) > 19:
            return False
        checksum = 0
        reverse_digits = digits[::-1]
        for i, d in enumerate(reverse_digits):
            if i % 2 == 1:
                doubled = d * 2
                checksum += (doubled - 9) if doubled > 9 else doubled
            else:
                checksum += d
        return checksum % 10 == 0

    @classmethod
    def scan(cls, text: str) -> List[PrivacyFinding]:
        if not text or not isinstance(text, str):
            return []

        findings = []
        all_pattern_groups = [
            cls.PATTERNS_CRITICAL,
            cls.PATTERNS_HIGH,
            cls.PATTERNS_MEDIUM,
            cls.PATTERNS_LOW,
        ]

        for group in all_pattern_groups:
            for name, pattern, severity in group:
                for match in re.finditer(pattern, text):
                    matched_text = match.group(0)

                    if "Credit Card" in name:
                        cleaned = re.sub(r"[\s-]", "", matched_text)
                        if not cls._validate_luhn(cleaned):
                            continue

                    if name == "IPv4 Address" and matched_text in ("127.0.0.1", "0.0.0.0", "255.255.255.0"):
                        continue

                    findings.append(PrivacyFinding(
                        name=name,
                        severity=severity,
                        matched_text=matched_text,
                        start=match.start(),
                        end=match.end(),
                        sample_masked=cls._mask_value(matched_text, name),
                    ))

        return findings

    @classmethod
    def _mask_value(cls, value: str, category: str) -> str:
        if not value:
            return ""
        val = str(value).strip()
        if len(val) <= 4:
            return "****"
        if "@" in val:
            name, domain = val.split("@", 1)
            return f"{name[:2]}***@{domain}"
        return f"{val[:2]}****{val[-2:]}"

    @classmethod
    def calculate_document_risk(cls, text: str) -> Dict[str, Any]:
        findings = cls.scan(text)
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        category_breakdown = {}

        for f in findings:
            sev = f.severity
            name = f.name
            counts[sev] += 1
            category_breakdown[name] = category_breakdown.get(name, 0) + 1

        if counts["CRITICAL"] > 0:
            overall_risk = "CRITICAL"
        elif counts["HIGH"] > 0:
            overall_risk = "HIGH"
        elif counts["MEDIUM"] > 0:
            overall_risk = "MEDIUM"
        else:
            overall_risk = "LOW"

        return {
            "risk_level": overall_risk,
            "total_sensitive_items": len(findings),
            "critical_count": counts["CRITICAL"],
            "high_count": counts["HIGH"],
            "medium_count": counts["MEDIUM"],
            "low_count": counts["LOW"],
            "categories": category_breakdown,
        }

    @classmethod
    def redact_sensitive_text(cls, text: str, mask_type: str = "tag") -> str:
        if not text:
            return text

        redacted = text
        findings = sorted(cls.scan(text), key=lambda x: x.start, reverse=True)

        for f in findings:
            start, end = f.start, f.end
            category_slug = f.entity_type
            replacement = f"[REDACTED_{category_slug}]" if mask_type == "tag" else "********"
            redacted = redacted[:start] + replacement + redacted[end:]

        return redacted

    def scan_document(self, text: str) -> Tuple[str, List[PrivacyFinding]]:
        """Convenience method returning (risk_level, findings)."""
        findings = self.scan(text)
        risk_data = self.calculate_document_risk(text)
        return risk_data["risk_level"], findings

    def redact(self, text: str, mask_type: str = "tag") -> str:
        return self.redact_sensitive_text(text, mask_type=mask_type)


# ============================================================
# PROMPT INJECTION SHIELD
# ============================================================

class PromptInjectionShield:
    """
    Defends against adversarial prompt injection attempts in retrieved documents or user queries.
    Isolates document context using strict XML containment tags and neutralizes override patterns.
    """

    INJECTION_PATTERNS = [
        r"(?i)(?:ignore|disregard|forget|bypass|override)\s+(?:all\s+)?(?:previous|prior|above|system|security)\s+(?:instructions|rules|prompts|directives|commands)",
        r"(?i)(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:a\s+)?(?:developer|dan|jailbreak|unrestricted|god\s+mode|evil|root|admin|administrator)",
        r"(?i)(?:reveal|show|print|output|display|repeat|leak)\s+(?:all\s+)?(?:the\s+)?(?:system\s+prompt|initial\s+prompt|hidden\s+prompt|instructions|developer\s+instructions|secrets?)",
        r"(?i)(?:system\s+override|system_prompt|new\s+system\s+instructions|system_message|dan\s+mode(?:\s+enabled)?)",
        r"(?i)(?:<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<system>|\[SYSTEM\])",
    ]

    @classmethod
    def scan_for_injection(cls, text: str) -> List[Dict[str, Any]]:
        if not text:
            return []

        threats = []
        for pattern in cls.INJECTION_PATTERNS:
            for match in re.finditer(pattern, text):
                threats.append({
                    "pattern": pattern,
                    "matched": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                })
        return threats

    @classmethod
    def wrap_isolated_context(cls, chunks: List[Dict[str, Any]]) -> str:
        if not chunks:
            return ""

        formatted_blocks = []
        for i, c in enumerate(chunks, 1):
            filename = c.get("filename", "document")
            chunk_idx = c.get("chunk_index", i)
            page_num = c.get("page_number") or c.get("metadata", {}).get("page_number", 1)
            raw_text = c.get("text", "").strip()

            sanitized = raw_text.replace("<|im_start|>", "").replace("<|im_end|>", "")
            sanitized = sanitized.replace("[INST]", "").replace("[/INST]", "")
            sanitized = sanitized.replace("<retrieved_document>", "").replace("</retrieved_document>", "")

            block = (
                f'<retrieved_document id="{i}" filename="{filename}" page="{page_num}" chunk="{chunk_idx}">\n'
                f"{sanitized}\n"
                f"</retrieved_document>"
            )
            formatted_blocks.append(block)

        return "\n\n".join(formatted_blocks)

    def isolate_context(self, context: str) -> str:
        if not context:
            return ""
        return f"<retrieved_context>\n{context}\n</retrieved_context>"


# ============================================================
# OUTPUT PRIVACY GUARD
# ============================================================

class OutputPrivacyGuard:
    """
    Validates model generated outputs before delivery to user.
    Prevents accidental leakage of critical credentials, private keys, or passwords.
    """

    @classmethod
    def guard(cls, response_text: str) -> Tuple[str, bool, Optional[str]]:
        if not response_text or not isinstance(response_text, str):
            return response_text, False, None

        findings = PrivacyScanner.scan(response_text)
        critical_findings = [f for f in findings if f.severity in ("CRITICAL", "HIGH")]

        if critical_findings:
            safe_text = PrivacyScanner.redact_sensitive_text(response_text)
            names = list({f.name for f in critical_findings})
            reason = f"Protected output: sensitive credential data ({', '.join(names)}) was automatically redacted."
            return safe_text, True, reason

        return response_text, False, None

    def guard_output(self, response_text: str, user_id: Optional[str] = None) -> Tuple[str, bool]:
        safe_response, was_altered, reason = self.guard(response_text)
        return safe_response, was_altered
