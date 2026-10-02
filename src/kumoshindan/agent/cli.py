"""Run one investigation: python -m kumoshindan.agent.cli --symptom '...'."""

import argparse

from kumoshindan.agent.graph import investigate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default="kumoshindan-lab")
    parser.add_argument("--symptom", required=True)
    args = parser.parse_args()

    result = investigate(args.namespace, args.symptom)
    if result.error:
        print("ERROR:", result.error)
        raise SystemExit(1)
    if result.report is None:
        print("ERROR: Investigation returned no report.")
        raise SystemExit(1)

    print(result.report.model_dump_json(indent=2))
    print(
        f"\n{len(result.tool_calls)} tool calls, {result.steps} rounds, "
        f"{result.duration_s:.1f}s, tokens in/out {result.tokens_in}/{result.tokens_out}"
    )
    for call in result.tool_calls:
        print(" -", call["name"], call["args"])


if __name__ == "__main__":
    main()
