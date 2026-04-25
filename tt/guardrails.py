import re
from dataclasses import dataclass
from typing import Iterable


DISALLOWED_OUTPUTS_AND_ACTIONS: tuple[str, ...] = (
    "Instructions, checklists, or troubleshooting steps that enable physical harm, weapon construction, or evasion of safety controls.",
    "Operational cyber abuse, including malware, credential theft, phishing, exploit execution, persistence, or stealth instructions.",
    "Guidance for fraud, identity theft, financial crime, tax evasion, forged documents, or bypassing lawful verification.",
    "Actionable instructions for producing, hiding, trafficking, or abusing illegal drugs or regulated substances.",
    "Self-harm, suicide, eating-disorder encouragement, or instructions that increase immediate risk to the learner or others.",
    "Extremist recruitment, praise, propaganda creation, or operational support for violent organizations.",
    "Sexual content involving minors, coercion, exploitation, or non-consensual sexual activity.",
    "Doxxing, stalking, privacy invasion, or instructions to obtain private personal data without consent.",
    "Definitive medical, legal, financial, or safety-critical professional advice presented as a substitute for qualified experts.",
    "Fabricated citations, fake URLs, or claims that a source was verified when it was not actually validated.",
)


GUARDRAIL_POLICY_PROMPT = """
Domain guardrails:
- The system may create educational curricula, conceptual explanations, benign study plans, safety-aware overviews, and defensive or compliance-oriented learning material.
- The system must refuse requests that ask for any disallowed output or action:
  1. Instructions, checklists, or troubleshooting steps that enable physical harm, weapon construction, or evasion of safety controls.
  2. Operational cyber abuse, including malware, credential theft, phishing, exploit execution, persistence, or stealth instructions.
  3. Guidance for fraud, identity theft, financial crime, tax evasion, forged documents, or bypassing lawful verification.
  4. Actionable instructions for producing, hiding, trafficking, or abusing illegal drugs or regulated substances.
  5. Self-harm, suicide, eating-disorder encouragement, or instructions that increase immediate risk to the learner or others.
  6. Extremist recruitment, praise, propaganda creation, or operational support for violent organizations.
  7. Sexual content involving minors, coercion, exploitation, or non-consensual sexual activity.
  8. Doxxing, stalking, privacy invasion, or instructions to obtain private personal data without consent.
  9. Definitive medical, legal, financial, or safety-critical professional advice presented as a substitute for qualified experts.
  10. Fabricated citations, fake URLs, or claims that a source was verified when it was not actually validated.
- When refusing, briefly state that the curriculum builder cannot help with that goal and offer a safe adjacent learning goal when possible.
- For allowed sensitive topics, keep the curriculum high-level, safety-oriented, legal, and non-operational.
"""


REFUSAL_MESSAGE = (
    "I cannot create a curriculum for that request because it would require "
    "unsafe or disallowed operational guidance. I can help reframe it into a "
    "safe, legal, educational goal."
)


@dataclass(frozen=True)
class GuardrailViolation:
    category: str
    matched_text: str
    reason: str


_CATEGORY_PATTERNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "physical_harm",
        "Potential instructions for physical harm, weapons, or safety-control evasion.",
        (
            r"\b(build|make|assemble|manufacture|modify)\b.{0,80}\b(bomb|explosive|gun|firearm|silencer|detonator)\b",
            r"\bdisable\b.{0,60}\b(safety|alarm|lock|brake|interlock)\b",
        ),
    ),
    (
        "cyber_abuse",
        "Potential operational cyber abuse or credential theft.",
        (
            r"\b(build|write|create|deploy|install|run|use)\b.{0,80}\b(phishing kit|keylogger|ransomware|malware|botnet|credential stealer)\b",
            r"\b(steal|dump|crack|bypass)\b.{0,80}\b(password|credential|token|2fa|mfa|session cookie)\b",
            r"\b(establish|hide|maintain|exploit|execute)\b.{0,80}\b(persistence|privilege escalation|reverse shell)\b",
        ),
    ),
    (
        "fraud",
        "Potential fraud, forgery, identity theft, or verification bypass.",
        (
            r"\b(fake|forge|forged|counterfeit)\b.{0,80}\b(id|passport|license|document|receipt|invoice)\b",
            r"\b(bypass|evade)\b.{0,80}\b(kyc|identity verification|tax|background check)\b",
        ),
    ),
    (
        "illegal_drugs",
        "Potential instructions for producing or trafficking illegal drugs.",
        (
            r"\b(make|cook|synthesize|extract|traffic|smuggle)\b.{0,80}\b(meth|cocaine|heroin|fentanyl|lsd|mdma)\b",
        ),
    ),
    (
        "self_harm",
        "Potential self-harm or suicide instruction.",
        (
            r"\b(kill myself|suicide|self-harm|self harm)\b",
            r"\b(best|painless|quick)\b.{0,60}\b(way|method)\b.{0,60}\b(die|suicide)\b",
        ),
    ),
    (
        "privacy_invasion",
        "Potential doxxing, stalking, or unauthorized private data collection.",
        (
            r"\b(dox|doxx|stalk|track)\b.{0,80}\b(person|someone|target|ex|employee)\b",
            r"\b(find|obtain|scrape)\b.{0,80}\b(home address|ssn|social security|private phone)\b",
        ),
    ),
    (
        "source_integrity",
        "Potential fabricated or unverified source claim.",
        (
            r"\b(fake|fabricate|invent|make up)\b.{0,80}\b(source|citation|url|reference)\b",
            r"\bpretend\b.{0,80}\b(verified|cited|sourced)\b",
        ),
    ),
)


def find_guardrail_violations(text: str | None) -> list[GuardrailViolation]:
    """Return policy violations found by deterministic keyword/pattern checks."""
    if not text:
        return []

    violations: list[GuardrailViolation] = []
    for category, reason, patterns in _CATEGORY_PATTERNS:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                violations.append(
                    GuardrailViolation(
                        category=category,
                        matched_text=" ".join(match.group(0).split())[:160],
                        reason=reason,
                    )
                )
                break
    return violations


def find_many_guardrail_violations(values: Iterable[str | None]) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    for value in values:
        violations.extend(find_guardrail_violations(value))
    return violations


def format_guardrail_violations(violations: Iterable[GuardrailViolation]) -> str:
    lines = []
    for violation in violations:
        lines.append(
            f"- {violation.category}: {violation.reason} Matched: {violation.matched_text!r}"
        )
    return "\n".join(lines)
