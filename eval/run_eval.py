"""Evaluate KumoShindan against the fault workloads already deployed in the cluster."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from kubesleuth.agent.graph import investigate
from kubesleuth.config import settings

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FILE = ROOT / "eval" / "expected.yaml"
RESULTS_DIR = ROOT / "eval" / "results"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="Run only the named cases")
    args = parser.parse_args()

    cases = yaml.safe_load(EXPECTED_FILE.read_text(encoding="utf-8")) or []
    if args.only:
        cases = [case for case in cases if case["name"] in args.only]
    if not cases:
        parser.error("No matching evaluation cases.")

    rows = []
    for case in cases:
        print(f"Running {case['name']}...", flush=True)
        result = investigate(case["namespace"], case["symptom"])
        report = result.report
        text = ""
        if report:
            text = (report.root_cause + " " + " ".join(report.evidence)).lower()

        category_ok = bool(report and report.category == case["category"])
        keywords = case.get("must_mention_any", [])
        keyword_ok = not keywords or any(word.lower() in text for word in keywords)

        row = {
            "scenario": case["name"],
            "expected": case["category"],
            "got": report.category if report else None,
            "category_ok": category_ok,
            "keyword_ok": keyword_ok,
            "duration_s": round(result.duration_s, 1),
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "report": report.model_dump(mode="json") if report else None,
            "tool_calls": result.tool_calls,
            "steps": result.steps,
            "error": result.error,
        }
        rows.append(row)
        print(
            f"  got={row['got']} category_ok={category_ok} "
            f"keyword_ok={keyword_ok} duration={row['duration_s']}s",
            flush=True,
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = {
        "model": f"{settings.llm_provider}:{settings.llm_model}",
        "date": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
    (RESULTS_DIR / f"{stamp}.json").write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )
    print(f"Saved results to eval/results/{stamp}.json")
    if not all(row["category_ok"] and row["keyword_ok"] and row["error"] is None for row in rows):
        raise SystemExit("Evaluation failed: one or more cases did not meet expectations.")


if __name__ == "__main__":
    main()
