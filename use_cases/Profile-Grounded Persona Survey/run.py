"""Run a profile-grounded task-delegation survey through the public Genesia SDK."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from genesia import load_task, preflight, run
from genesia.schemas import TaskSpec

HERE = Path(__file__).resolve().parent


def build_task(args: argparse.Namespace) -> TaskSpec:
    data = load_task(args.task).model_dump()
    data["cohort"]["source"] = str(args.personas.resolve())
    ids = args.persona_id
    if ids is None:
        ids = [] if args.count is not None else data["cohort"]["ids"]
    if len(ids) != len(set(ids)):
        raise ValueError("--persona-id values must be unique")
    if ids and args.count is not None and args.count != len(ids):
        raise ValueError("--count must match the number of explicit Persona IDs")
    count = len(ids) if ids else args.count if args.count is not None else data["cohort"]["size"]
    data["cohort"].update(ids=ids, size=count)
    data["study"]["min_personas"] = count
    for field in ("model", "base_url", "api_key_env"):
        if value := getattr(args, field):
            data["model"][field] = value
    if args.language:
        data["insight"]["language"] = args.language
    if args.output_dir:
        data["output_dir"] = str(args.output_dir.resolve())
    if args.allow_model_data:
        data["permissions"].update(send_persona=True, send_materials=True)
    task = TaskSpec.model_validate(data)
    if task.environment.mode != "survey" or any(method.kind != "survey" for method in task.methods):
        raise ValueError("This case requires survey-only input and survey methods")
    return task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, default=HERE / "task.yaml")
    parser.add_argument("--personas", type=Path, required=True, help="Authorized Persona JSON/TSV")
    parser.add_argument("--persona-id", action="append", help="Exact ID; repeat for a fixed cohort")
    parser.add_argument("--count", type=int, help="Sample size, or exact explicit-ID count")
    parser.add_argument("--model", default=os.environ.get("GENESIA_MODEL"))
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"))
    parser.add_argument("--api-key-env", help="Environment variable containing the key, not the key itself")
    parser.add_argument("--language", choices=("en", "zh-CN"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--allow-model-data", action="store_true", help="Permit profile and questionnaire sending"
    )
    parser.add_argument("--preflight", action="store_true", help="Validate without model inference")
    parser.add_argument("--network", action="store_true", help="Check the catalog with --preflight")
    args = parser.parse_args(argv)
    if args.network and not args.preflight:
        parser.error("--network requires --preflight")
    try:
        task = build_task(args)
        if args.preflight:
            checks = preflight(task, network=args.network)
            print(json.dumps(checks, ensure_ascii=False, indent=2))
            return 0 if checks["ok"] else 1
        result = run(task)
        print(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "status": result.status,
                    "output_dir": result.output_dir,
                    "report": str(Path(result.output_dir) / "report.html"),
                    "episode_modes": sorted({episode.mode for episode in result.episodes}),
                    "metrics": result.metrics,
                    "errors": result.errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if result.status == "completed" else 1
    except (OSError, ValueError) as error:
        print(f"Cannot run task-delegation survey: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
