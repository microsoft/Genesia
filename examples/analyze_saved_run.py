"""Generate a staged insight report from one immutable saved Genesia run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from genesia import analyze
from genesia.schemas import InsightSpec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--language", choices=["en", "zh-CN"])
    parser.add_argument("--focus", action="append", default=[])
    args = parser.parse_args()

    manifest = json.loads((args.run_dir / "run_manifest.json").read_text("utf-8"))
    settings = {
        **manifest["task"].get("insight", {}),
    }
    settings.pop("strategy", None)
    if args.language:
        settings["language"] = args.language
    if args.focus:
        settings["focus"] = args.focus
    result = analyze(
        args.run_dir,
        insight=InsightSpec.model_validate(settings),
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "status": result.status,
                "report": str(Path(result.output_dir) / "report.html"),
                "errors": result.errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
