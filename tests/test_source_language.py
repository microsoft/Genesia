import hashlib
import json
import os
import re
from pathlib import Path

import pytest

from genesia.live import model_visible_text

ROOT = Path(__file__).resolve().parents[1]
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]")
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html", ".css", ".ps1", ".sh"}
EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "local",
    "node_modules",
    "runs",
    "sample",
}
PROTOTYPE = Path("use_cases") / "Live Prototype Comparison"
FROZEN_LOCALIZED_SOURCES = {
    "src/App.tsx",
    "src/data.ts",
    "src/i18n/state.ts",
    "src/workspace.ts",
    "tests/browser/board.spec.ts",
    "tests/browser/journeys.spec.ts",
    "tests/workspace.test.mjs",
}


def test_source_uses_english_text_with_explicit_unicode_fixtures():
    frozen_sources = None
    for source_root in (".github", "src", "tests", "examples", "use_cases"):
        for folder, directories, filenames in os.walk(ROOT / source_root):
            directories[:] = sorted(set(directories) - EXCLUDED_DIRECTORIES)
            for filename in sorted(filenames):
                path = Path(folder) / filename
                packaged_policy = path.parent == ROOT / "src" / "genesia" / "resources"
                if path.suffix not in SOURCE_SUFFIXES and not (packaged_policy and path.suffix == ".md"):
                    continue
                relative = path.relative_to(ROOT)
                if not HAN.search(path.read_text(encoding="utf-8")):
                    continue
                prototype_root = ROOT / PROTOTYPE / "prototype"
                if path.is_relative_to(prototype_root):
                    source = path.relative_to(prototype_root).as_posix()
                    if source in FROZEN_LOCALIZED_SOURCES:
                        if frozen_sources is None:
                            manifest = ROOT / PROTOTYPE / "sample" / "prototype.json"
                            frozen_sources = json.loads(manifest.read_text("utf-8"))["source_files_sha256"]
                        assert hashlib.sha256(path.read_bytes()).hexdigest() == frozen_sources[source], (
                            relative
                        )
                        continue
                pytest.fail(f"Use English source text or an explicit Unicode fixture: {relative}")


@pytest.mark.parametrize(
    "relative",
    [
        ("examples", "new_example.py"),
        ("use_cases", "new_case", "run.py"),
        ("use_cases", "new_case", "src", "app.ts"),
        ("use_cases", "Live Prototype Comparison", "prototype", "src", "new.ts"),
        ("src", "genesia", "resources", "new_policy.md"),
    ],
)
def test_language_guard_checks_new_source_roots(tmp_path, monkeypatch, relative):
    source = tmp_path.joinpath(*relative)
    source.parent.mkdir(parents=True)
    source.write_text("# \u4e2d\u6587\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "ROOT", tmp_path)

    with pytest.raises(pytest.fail.Exception, match=source.name):
        test_source_uses_english_text_with_explicit_unicode_fixtures()


def test_language_guard_ignores_dependencies_and_private_outputs(tmp_path, monkeypatch):
    for directory in ("node_modules", "dist", "local", "runs", "sample"):
        source = tmp_path / "use_cases" / "new_case" / directory / "fixture.js"
        source.parent.mkdir(parents=True)
        source.write_text("// \u4e2d\u6587\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "ROOT", tmp_path)

    test_source_uses_english_text_with_explicit_unicode_fixtures()


@pytest.mark.parametrize("hash_matches", [False, True])
def test_localized_prototype_exception_requires_frozen_hash(tmp_path, monkeypatch, hash_matches):
    source = tmp_path / PROTOTYPE / "prototype" / "src" / "workspace.ts"
    source.parent.mkdir(parents=True)
    source.write_text("// \u4e2d\u6587\n", encoding="utf-8")
    manifest = tmp_path / PROTOTYPE / "sample" / "prototype.json"
    manifest.parent.mkdir()
    expected_hash = hashlib.sha256(source.read_bytes()).hexdigest() if hash_matches else "0" * 64
    manifest.write_text(
        json.dumps({"source_files_sha256": {"src/workspace.ts": expected_hash}}),
        encoding="utf-8",
    )
    monkeypatch.setitem(globals(), "ROOT", tmp_path)

    if hash_matches:
        test_source_uses_english_text_with_explicit_unicode_fixtures()
    else:
        with pytest.raises(AssertionError, match=source.name):
            test_source_uses_english_text_with_explicit_unicode_fixtures()


def test_model_visible_text_removes_icon_font_glyphs_only():
    text = "Settings\n\ue70e\n78°F\n\u4e2d\u6587\u754c\u9762\nColors \U000f0001 label\n\ue765"
    assert model_visible_text(text) == "Settings\n78°F\n\u4e2d\u6587\u754c\u9762\nColors label"
