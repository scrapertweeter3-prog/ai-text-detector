#!/usr/bin/env python3
"""detectext - stylometric AI-text detector.

Scores text 0-100 for machine-shaped writing using surface signals only:
sentence burstiness, contraction rate, formal-connective density, opener
repetition, punctuation variety, vocabulary repetition. Stdlib only, no
network, no model files. It is a screening tool, not a verdict.

Usage:
  python3 detectext.py file.txt [more.txt ...]
  cat note.txt | python3 detectext.py
  python3 detectext.py --json folder/*.txt
  python3 detectext.py --threshold 70 draft.txt   # exit 1 if score >= 70
"""
import argparse
import json
import re
import sys
from pathlib import Path

WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

CONTRACTION = re.compile(
    r"\b\w+n['\u2019]t\b"
    r"|\b(?:i|you|we|they|he|she|it|that|there|what|who)['\u2019](?:m|re|s|ll|ve|d)\b",
    re.IGNORECASE,
)

CONNECTIVES = [
    "in conclusion", "moreover", "furthermore", "additionally",
    "it is important to note", "it's worth noting", "it is worth noting",
    "in today's", "in the modern", "in the digital", "ever-evolving",
    "plays a crucial role", "plays a vital role", "delve into",
    "navigate the", "a testament to", "in summary", "overall,",
    "when it comes to", "it's important to remember",
]

AI_OPENER = re.compile(
    r"^(?:in today's|in the (?:modern|digital|ever-evolving|current)"
    r"|it is (?:important|worth)|it's (?:important|worth)"
    r"|moreover|furthermore|additionally|in conclusion|overall)"
    r"\b",
    re.IGNORECASE,
)

PUNCT_KINDS = set(";:!?()[]{}\"'\u2014\u2013-*/&#@%")

WEIGHTS = {
    "burstiness": 0.28,
    "connectives": 0.22,
    "contractions": 0.18,
    "openers": 0.12,
    "punctuation": 0.10,
    "repetition": 0.10,
}

MIN_WORDS = 40


def clamp01(x):
    return max(0.0, min(1.0, x))


def analyze(text):
    words = WORD.findall(text)
    if len(words) < MIN_WORDS:
        return {"error": "too short", "words": len(words),
                "note": f"need at least {MIN_WORDS} words for a stable score"}

    sentences = [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]
    lens = [len(WORD.findall(s)) for s in sentences] or [1]
    mean_len = sum(lens) / len(lens)
    var = sum((n - mean_len) ** 2 for n in lens) / len(lens)
    sd = var ** 0.5
    burst_ratio = (sd / mean_len) if mean_len else 0.0
    # human prose swings hard between short punches and long rambles;
    # uniform mid-length sentences are the machine tell
    burstiness_ai = clamp01(1.0 - burst_ratio / 0.65)

    low = text.lower()
    conn_hits = [p for p in CONNECTIVES if p in low]
    conn_rate = (len(conn_hits) / len(sentences)) * 100.0
    connectives_ai = clamp01(conn_rate / 8.0)

    contractions = len(CONTRACTION.findall(text))
    contr_rate = contractions / len(words) * 100.0
    # informal human writing contracts constantly; polished output doesn't
    contractions_ai = clamp01(1.0 - contr_rate / 2.5)

    openers = sum(1 for s in sentences if AI_OPENER.match(s))
    opener_rate = openers / len(sentences)
    openers_ai = clamp01(opener_rate / 0.35)

    puncts = [c for c in text if c in PUNCT_KINDS]
    variety = (len(set(puncts)) / len(puncts)) if puncts else 0.0
    punctuation_ai = clamp01(1.0 - variety / 0.55)

    windows = [words[i:i + 100] for i in range(0, len(words) - 99, 50)] \
        or [words[:100]]
    ttrs = [len({w.lower() for w in win}) / len(win) for win in windows]
    mean_ttr = sum(ttrs) / len(ttrs)
    # mid-range repetition reads templated; both extremes read human
    repetition_ai = clamp01(1.0 - abs(mean_ttr - 0.66) / 0.14)

    score = 100.0 * sum(WEIGHTS[k] * v for k, v in {
        "burstiness": burstiness_ai,
        "connectives": connectives_ai,
        "contractions": contractions_ai,
        "openers": openers_ai,
        "punctuation": punctuation_ai,
        "repetition": repetition_ai,
    }.items())

    flags = []
    if burst_ratio < 0.35:
        flags.append(f"flat sentence rhythm (stdev/mean {burst_ratio:.2f})")
    if contractions == 0:
        flags.append("zero contractions in the whole sample")
    if conn_hits:
        flags.append("formal connectives: " + ", ".join(sorted(set(conn_hits))))
    if opener_rate >= 0.3:
        flags.append(f"templated openers on {openers}/{len(sentences)} sentences")

    if score >= 70:
        verdict = "machine-shaped"
    elif score >= 45:
        verdict = "mixed signals"
    else:
        verdict = "human-shaped"

    return {
        "score": round(score, 1),
        "verdict": verdict,
        "words": len(words),
        "sentences": len(sentences),
        "sentence_mean_len": round(mean_len, 1),
        "sentence_len_stdev": round(sd, 1),
        "burstiness_ratio": round(burst_ratio, 2),
        "contractions": contractions,
        "contractions_per_100w": round(contr_rate, 2),
        "connective_hits": sorted(set(conn_hits)),
        "ai_openers": openers,
        "punct_variety": round(variety, 2),
        "mean_ttr_100w": round(mean_ttr, 2),
        "flags": flags,
    }


def render(res):
    if "error" in res:
        return f"skip: {res['note']} ({res['words']} words)"
    lines = [
        f"Words: {res['words']} in {res['sentences']} sentences",
        f"Sentence length: {res['sentence_mean_len']} avg, "
        f"{res['sentence_len_stdev']} stdev "
        f"(burstiness ratio {res['burstiness_ratio']})",
        f"Contractions: {res['contractions_per_100w']} per 100 words",
        f"Formal connectives: "
        f"{', '.join(res['connective_hits']) if res['connective_hits'] else 'none'}",
        f"Templated openers: {res['ai_openers']}/{res['sentences']} sentences",
        f"Punctuation variety: {res['punct_variety']}",
        f"AI-LIKELIHOOD: {res['score']}/100  {res['verdict']}",
    ]
    for f in res["flags"]:
        lines.append(f"  flag: {f}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="detectext",
                                 description="stylometric AI-text detector")
    ap.add_argument("paths", nargs="*", help="files to score (default: stdin)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--threshold", type=int, default=70,
                    help="exit 1 when any score reaches this (default 70)")
    args = ap.parse_args(argv)

    if args.paths:
        texts = []
        for p in args.paths:
            path = Path(p)
            if path.is_dir():
                texts.extend(sorted(path.glob("*.txt")))
            else:
                texts.append(path)
        samples = [(str(t), t.read_text(encoding="utf-8", errors="replace"))
                   for t in texts]
    else:
        samples = [("<stdin>", sys.stdin.read())]

    results = []
    for name, text in samples:
        res = analyze(text)
        res["file"] = name
        results.append(res)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for res in results:
            print(f"== {res['file']}")
            print(render(res))
            print()

    worst = max((r["score"] for r in results if "score" in r), default=0)
    return 1 if worst >= args.threshold else 0


if __name__ == "__main__":
    sys.exit(main())
