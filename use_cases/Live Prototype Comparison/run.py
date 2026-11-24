"""Compare Agent-work supervision designs through Genesia's public SDK."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from genesia import load_task, preflight, run
from genesia.schemas import TaskSpec

HERE = Path(__file__).resolve().parent
PROTOTYPE_DIST = HERE / "prototype" / "dist"


@contextmanager
def local_prototype() -> Iterator[str]:
    if not (PROTOTYPE_DIST / "index.html").is_file():
        raise ValueError(
            "Bundled prototype is not built. From the repository root, run "
            '`npm ci --prefix "use_cases/Live Prototype Comparison/prototype"` and '
            '`npm run build --prefix "use_cases/Live Prototype Comparison/prototype"`. '
            "The prototype requires a repository checkout; it is not included in the Python package."
        )
    handler = partial(SimpleHTTPRequestHandler, directory=str(PROTOTYPE_DIST))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    try:
        thread.start()
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        if thread.is_alive():
            server.shutdown()
            thread.join()
        server.server_close()


def check_local_prototype(task: TaskSpec) -> None:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for url, design in zip(
                    [task.environment.start_url, *task.environment.handoff_urls], ["b", "d"], strict=True
                ):
                    context = browser.new_context()
                    try:
                        page = context.new_page()
                        response = page.goto(url, wait_until="networkidle", timeout=30000)
                        if response is None or response.status != 200:
                            raise ValueError(f"Bundled prototype did not return HTTP 200: {url}")
                        page.locator(
                            f'[data-prototype-ready="true"][data-design="{design}"][data-research="true"]'
                        ).wait_for(state="visible", timeout=30000)
                    finally:
                        context.close()
            finally:
                browser.close()
    except PlaywrightError as error:
        raise ValueError(
            f"Bundled prototype browser readiness failed: {error}. "
            "Install the live extra and Chromium as described in the case README."
        ) from error


def build_task(args: argparse.Namespace) -> TaskSpec:
    data = load_task(args.task).model_dump()
    data["cohort"]["source"] = str(args.personas.resolve())
    ids = args.persona_id
    if ids is None:
        ids = [] if args.count is not None else data["cohort"]["ids"]
    if ids and len(ids) != len(set(ids)):
        raise ValueError("--persona-id values must be unique")
    if ids and args.count is not None and args.count != len(ids):
        raise ValueError("--count must match the number of explicit Persona IDs")
    count = len(ids) if ids else args.count if args.count is not None else data["cohort"]["size"]
    data["cohort"].update(ids=ids, size=count)
    data["study"]["min_personas"] = count
    if args.url_a:
        data["environment"]["start_url"] = args.url_a
    if args.url_b:
        data["environment"]["handoff_urls"] = [args.url_b]
    if args.model:
        data["model"]["model"] = args.model
    if args.base_url:
        data["model"]["base_url"] = args.base_url
    if args.api_key_env:
        data["model"]["api_key_env"] = args.api_key_env
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
    parser.add_argument("--persona-id", action="append", help="Exact ID; repeat to select a fixed cohort")
    parser.add_argument("--count", type=int, help="Sample size, or exact explicit-ID count")
    parser.add_argument("--url-a", help="First version (Design A) URL on the authorized origin")
    parser.add_argument("--url-b", help="Second version (Design B) URL on the same origin")
    parser.add_argument(
        "--local-prototype",
        action="store_true",
        help="Serve the built bundled A/B prototype on an isolated loopback port for this invocation",
    )
    parser.add_argument(
        "--model", default=os.environ.get("GENESIA_MODEL"), help="Model ID; no fallback is used"
    )
    parser.add_argument(
        "--base-url", default=os.environ.get("OPENAI_BASE_URL"), help="OpenAI-compatible API root"
    )
    parser.add_argument("--api-key-env", help="Environment variable containing the API key")
    parser.add_argument(
        "--language", choices=("en", "zh-CN"), help="Report prose language; otherwise keep the task setting"
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--allow-model-data", action="store_true", help="Permit profile/material/image sending"
    )
    parser.add_argument("--preflight", action="store_true", help="Validate without inference")
    parser.add_argument(
        "--network", action="store_true", help="Also check the model catalog during preflight"
    )
    args = parser.parse_args(argv)
    if args.network and not args.preflight:
        parser.error("--network is a preflight option; use it with --preflight")
    if args.local_prototype and (args.url_a or args.url_b):
        parser.error("--local-prototype cannot be combined with --url-a or --url-b")
    try:
        task = build_task(args)
        if args.local_prototype and (
            task.environment.mode != "live" or task.environment.candidate_labels != ["Design A", "Design B"]
        ):
            raise ValueError("--local-prototype requires the live Design A then Design B protocol")
        # Check permissions, cohort, browser dependencies and budgets before starting the server.
        if args.local_prototype:
            checks = preflight(task)
            if not checks["ok"]:
                print(json.dumps(checks, ensure_ascii=False, indent=2))
                return 1
        with local_prototype() if args.local_prototype else nullcontext(None) as origin:
            if origin is not None:
                data = task.model_dump()
                data["environment"].update(
                    start_url=f"{origin}/?design=b&research=1",
                    handoff_urls=[f"{origin}/?design=d&research=1"],
                )
                task = TaskSpec.model_validate(data)
                check_local_prototype(task)
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
                        "report": str(Path(result.output_dir) / "report.html"),
                        "valid_responses": result.metrics["valid_responses"],
                        "invalid_responses": result.metrics["invalid_responses"],
                        "missing_responses": result.metrics["missing_responses"],
                        "errors": result.errors,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if result.status == "completed" else 1
    except (OSError, ValueError) as error:
        print(f"Cannot run agent-work supervision comparison: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
