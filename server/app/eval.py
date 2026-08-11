"""Evaluation harness for classification quality (J1-93353 §7 AI accuracy).

Measures agreement with a human gold set and enforces the hard gate: a *failed* or
*out-of-scope* conversation labelled *resolved* is a CRITICAL failure. Adjacent-category
confusion is tolerated. Run live against the configured classifier:

    python -m app.eval        # uses Vertex when configured, else deterministic rules
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .domain.models import AnalysisRecord, Category, Conversation
from .fixtures import CONVERSATIONS

Classifier = Callable[[Conversation, str, str], AnalysisRecord]

DEFAULT_THRESHOLD = 0.85

# Human-labelled gold set (expand to 100-200 real conversations for a real measurement).
GOLD: dict[str, Category] = {
    "11111111-1111-4111-8111-111111111111": "resolved",
    "22222222-2222-4222-8222-222222222222": "failed_to_resolve",
    "33333333-3333-4333-8333-333333333333": "positive_feedback",
    "44444444-4444-4444-8444-444444444444": "negative_feedback",
    "55555555-5555-4555-8555-555555555555": "out_of_scope",
    "66666666-6666-4666-8666-666666666666": "resolved",
}

# Mislabelling any of these true categories as "resolved" is a critical failure.
_CRITICAL_TRUE = {"failed_to_resolve", "out_of_scope"}


@dataclass
class EvalReport:
    total: int
    agreements: int
    confusion: dict[tuple[str, str], int] = field(default_factory=dict)  # (expected, predicted)->n
    critical_failures: list[tuple[str, str, str]] = field(default_factory=list)  # (id, exp, pred)

    @property
    def agreement(self) -> float:
        return self.agreements / self.total if self.total else 0.0

    def passed(self, threshold: float = DEFAULT_THRESHOLD) -> bool:
        return self.agreement >= threshold and not self.critical_failures


def evaluate(
    classify: Classifier,
    conversations: list[Conversation] = CONVERSATIONS,
    gold: dict[str, Category] = GOLD,
) -> EvalReport:
    report = EvalReport(total=0, agreements=0)
    for conv in conversations:
        expected = gold.get(conv.id)
        if expected is None:
            continue
        predicted = classify(conv, "eval", "eval").category
        report.total += 1
        report.confusion[(expected, predicted)] = report.confusion.get((expected, predicted), 0) + 1
        if predicted == expected:
            report.agreements += 1
        if expected in _CRITICAL_TRUE and predicted == "resolved":
            report.critical_failures.append((conv.id, expected, predicted))
    return report


def main() -> int:
    from .gemini import make_classifier

    report = evaluate(make_classifier())
    print(f"agreement: {report.agreement:.0%} ({report.agreements}/{report.total})")
    if report.critical_failures:
        print("CRITICAL (labelled resolved):")
        for cid, exp, _ in report.critical_failures:
            print(f"  {cid[:8]} expected {exp}, got resolved")
    print("RESULT:", "PASS" if report.passed() else "FAIL")
    return 0 if report.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
