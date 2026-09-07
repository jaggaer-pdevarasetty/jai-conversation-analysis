"""Evaluation harness for classification quality (J1-93353 §7 AI accuracy).

Measures agreement with a human gold set and enforces the hard gate: a *failed* or
*out-of-scope* conversation labelled *resolved* is a CRITICAL failure. Adjacent-category
confusion is tolerated. Run live against the configured classifier:

    python -m app.eval        # uses Vertex when configured, else deterministic rules
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .domain.models import CATEGORIES, AnalysisRecord, Category, Conversation
from .fixtures import CONVERSATIONS

Classifier = Callable[[Conversation, str, str], AnalysisRecord]

DEFAULT_THRESHOLD = 0.85

# Seed gold set (fixtures). Grow the REAL set by adding human-labelled conversations to
# server/eval_gold.json — target 100-200 records for a statistically meaningful ≥85% measure.
GOLD: dict[str, Category] = {
    "11111111-1111-4111-8111-111111111111": "resolved",
    "22222222-2222-4222-8222-222222222222": "failed_to_resolve",
    "33333333-3333-4333-8333-333333333333": "positive_feedback",
    "44444444-4444-4444-8444-444444444444": "negative_feedback",
    "55555555-5555-4555-8555-555555555555": "out_of_scope",
    "66666666-6666-4666-8666-666666666666": "resolved",
}

# External, version-controlled gold set — reviewers add labelled real conversations here
# without touching code. Format: [{"conversation_id": "...", "category": "..."}, ...]
GOLD_FILE = Path(__file__).resolve().parent.parent / "eval_gold.json"


def load_gold() -> dict[str, Category]:
    """The human-labelled gold set: eval_gold.json when present (grown by reviewers),
    else the built-in fixture seed. Invalid entries are rejected loudly, not silently."""
    if not GOLD_FILE.exists():
        return dict(GOLD)
    entries = json.loads(GOLD_FILE.read_text())
    if not isinstance(entries, list):
        raise ValueError(f"{GOLD_FILE.name}: expected a JSON array of {{conversation_id, category}}")
    gold: dict[str, Category] = {}
    for i, entry in enumerate(entries):
        cid, cat = entry.get("conversation_id"), entry.get("category")
        if not cid or cat not in CATEGORIES:
            raise ValueError(f"{GOLD_FILE.name}: entry {i} is invalid ({cid!r} -> {cat!r})")
        gold[cid] = cat
    return gold or dict(GOLD)

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
    gold: dict[str, Category] | None = None,
) -> EvalReport:
    gold = gold if gold is not None else load_gold()
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
    from .domain.analyze import analyze as rules_analyze
    from .gemini import make_batch_analyzer

    batch = make_batch_analyzer()  # Vertex when configured, else deterministic rules

    def classify(conv, run_id, now):
        records = batch([conv], run_id, now)
        return records[0] if records else rules_analyze(conv, run_id, now)

    gold = load_gold()
    report = evaluate(classify, gold=gold)
    print(f"gold set: {len(gold)} labelled conversations ({GOLD_FILE.name if GOLD_FILE.exists() else 'built-in seed'})")
    print(f"agreement: {report.agreement:.0%} ({report.agreements}/{report.total})")
    if report.critical_failures:
        print("CRITICAL (labelled resolved):")
        for cid, exp, _ in report.critical_failures:
            print(f"  {cid[:8]} expected {exp}, got resolved")
    print("RESULT:", "PASS" if report.passed() else "FAIL")
    return 0 if report.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
