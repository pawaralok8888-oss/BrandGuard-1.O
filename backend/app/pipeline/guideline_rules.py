"""Turn the explicit lines of an uploaded guideline into draft rule patterns.

Only explicit forms are converted, and no AI model is called. Everything else is returned as
unparsed, so a person can write that rule by hand. Every candidate is saved as an inactive
draft and only affects checks after a manager approves it.

Recognised forms, read from bullets under a heading:

  Under a prohibitive heading (PROHIBITED, AVOID, FORBIDDEN, BANNED, NEVER, DON'T):
    - "miracle" (use: "effective" or "clinically proven")   -> phrase, replacement "effective"
    - "drug" in product context                              -> phrase, context kept in note

  Under a DISCLAIMER heading, a quoted full sentence (4+ words, ending with a full stop):
    - All skincare products: "Results may vary. Individual skin types may respond differently."
      -> required_text

Quoted bullets under any other heading (for example APPROVED TERMINOLOGY) are not rules. They
are unparsed, because they name approved things and are not prohibitions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

QUOTE = re.compile(r'"([^"]+)"')
USE_CLAUSE = re.compile(r"\(use:\s*([^)]*)\)", re.IGNORECASE)
HEADING = re.compile(r"^[A-Z][A-Z0-9 &/'\-]*:$")
BULLET = re.compile(r"^\s*[-*\u2022]\s+(.*)$")
PROHIBITIVE = re.compile(r"PROHIBIT|AVOID|FORBID|BANNED|NEVER|DON'?T|DO NOT")
DISCLAIMER = re.compile(r"DISCLAIMER")
MIN_SENTENCE_WORDS = 4
MAX_TERM_LENGTH = 80


@dataclass(frozen=True)
class RuleCandidate:
    kind: str  # "phrase" or "required_text": the kinds the rule engine reads from rule_patterns
    pattern: str
    replacement: str = ""
    note: str = ""


@dataclass
class ExtractionResult:
    candidates: list[RuleCandidate] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)


def _phrase_candidate(item: str, term: str) -> RuleCandidate | None:
    if not term.strip() or len(term) > MAX_TERM_LENGTH:
        return None

    replacement, notes = "", []
    use = USE_CLAUSE.search(item)
    if use:
        options = QUOTE.findall(use.group(1))
        if options:
            replacement = options[0]
            if len(options) > 1:
                notes.append("Alternatives: " + ", ".join(options[1:]))
        rest = (item[: use.start()] + item[use.end():])
    else:
        rest = item

    # Text after the quoted term (other than the use clause) is context, such as "in product context".
    after_term = rest.split(f'"{term}"', 1)[-1].strip(" .,;:-")
    if after_term:
        notes.insert(0, after_term)

    return RuleCandidate(kind="phrase", pattern=term, replacement=replacement, note="; ".join(notes))


def _required_text_candidate(item: str, sentence: str) -> RuleCandidate | None:
    if len(sentence.split()) < MIN_SENTENCE_WORDS or not sentence.rstrip().endswith("."):
        return None
    label = item.split('"', 1)[0].strip(" :-")
    note = f"Applies to: {label}" if label else ""
    return RuleCandidate(kind="required_text", pattern=sentence, note=note)


def extract_rule_candidates(text: str) -> ExtractionResult:
    result = ExtractionResult()
    heading = ""

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if HEADING.match(line):
            heading = line.rstrip(":")
            continue

        bullet = BULLET.match(raw)
        if bullet is None:
            continue  # prose is not turned into rules

        item = bullet.group(1).strip()
        quotes = QUOTE.findall(item)
        candidate = None
        if quotes:
            if DISCLAIMER.search(heading):
                candidate = _required_text_candidate(item, quotes[0])
            elif PROHIBITIVE.search(heading):
                candidate = _phrase_candidate(item, quotes[0])

        if candidate is None:
            result.unparsed.append(item)
        else:
            result.candidates.append(candidate)

    return result
