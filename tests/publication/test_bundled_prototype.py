import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

pytestmark = pytest.mark.publication
CASE = Path(__file__).resolve().parents[2] / "use_cases" / "Live Prototype Comparison"


def test_bundled_prototype_preserves_frozen_ui_and_public_dependencies():
    manifest = json.loads((CASE / "sample" / "prototype.json").read_text(encoding="utf-8"))
    root = CASE / "prototype"
    for name, digest in manifest["source_files_sha256"].items():
        if name in {"package.json", "package-lock.json"}:
            continue
        source = root / ("frozen/main.tsx.snapshot" if name == "src/main.tsx" else name)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, name
    original_entrypoint = (root / "frozen" / "main.tsx.snapshot").read_text(encoding="utf-8")
    assert (root / "src" / "main.tsx").read_text(encoding="utf-8") == original_entrypoint.replace(
        "import './design-d.css'\n",
        "import './design-d.css'\nimport './contrast-fix.css'\n",
        1,
    )
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    assert package["license"] == "MIT" and package["private"]
    assert package["scripts"]["test"] == "node --test tests/workspace.test.mjs"
    assert lock["packages"][""]["dependencies"] == package["dependencies"]
    assert lock["packages"][""]["devDependencies"] == package["devDependencies"]
    for entry in lock["packages"].values():
        if "resolved" in entry:
            url = urlsplit(entry["resolved"])
            assert url.scheme == "https" and url.netloc == "registry.npmjs.org"
            assert entry["integrity"]
