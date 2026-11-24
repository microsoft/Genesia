"""Study Design A from a specification and screenshots through the public SDK."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from genesia import load_task, preflight, prepare, run
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
        value = getattr(args, field)
        if value:
            data["model"][field] = value
    if args.language:
        data["insight"]["language"] = args.language
    if args.output_dir:
        data["output_dir"] = str(args.output_dir.resolve())
    if args.allow_model_data:
        data["permissions"].update(send_persona=True, send_materials=True, send_screenshots=True)
    return TaskSpec.model_validate(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, default=HERE / "task.yaml")
    parser.add_argument("--personas", type=Path, required=True, help="Authorized Persona JSON/TSV")
    parser.add_argument("--persona-id", action="append", help="Exact ID; repeat for a fixed cohort")
    parser.add_argument("--count", type=int, help="Sample size, or exact explicit-ID count")
    parser.add_argument("--model", default=os.environ.get("GENESIA_MODEL"))
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"))
    parser.add_argument("--api-key-env", help="Environment variable containing the key, never the key itself")
    parser.add_argument("--language", choices=("en", "zh-CN"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--allow-model-data", action="store_true", help="Permit profile/material/image sending"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true", help="Validate without model inference")
    mode.add_argument(
        "--prepare", action="store_true", help="Build and review the environment; invokes models"
    )
    parser.add_argument("--network", action="store_true", help="Check the catalog with --preflight")
    args = parser.parse_args(argv)
    if args.network and not args.preflight:
        parser.error("--network requires --preflight")
    try:
        task = build_task(args)
        if task.environment.mode != "auto":
            raise ValueError("This material case requires environment.mode: auto")
        if args.preflight:
            checks = preflight(task, network=args.network)
            print(json.dumps(checks, ensure_ascii=False, indent=2))
            return 0 if checks["ok"] else 1
        if args.prepare:
            result = prepare(task)
            environment = result.get("environment_build", {})
            graph = environment.get("graph") or {}
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "output_dir": result["output_dir"],
                        "environment_level": environment.get("level"),
                        "states": len(graph.get("nodes", [])),
                        "transitions": len(graph.get("edges", [])),
                        "issues": environment.get("issues", []),
                        "research_readiness": result.get("research_readiness"),
                        "budget": result["budget"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if result["status"] == "ready" else 1
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
        print(f"Cannot run Dayline material study: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
