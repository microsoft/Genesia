# CI Configuration

The [workflow](../.github/workflows/ci.yml) runs for pull requests and pushes to
`main`. It uses disposable GitHub-hosted `windows-latest` runners with Python
3.11 and 3.12. Windows with Chromium remains the verified platform; this is not
a claim of tested Linux or macOS support.

Each matrix job installs declared dependencies and Chromium, runs lint and the
complete SDK suite (including the `browser` and `media` groups), builds the
distribution, installs the wheel without editable source, and reruns that suite.
The Python 3.12 job also runs the `publication` audit once against the full checkout
and runs default SDK tests from an extracted source distribution.
Tests use fake model gateways and local fixtures, not paid inference, private
datasets, production accounts or external prototype repositories.

The Linux `prototype` job builds the bundled frontend, runs its deterministic
state tests and exercises the SDK's local prototype integration. A separate
Windows `prototype-ui` job uses Node.js 22 and Microsoft Edge to run the complete
frontend browser suite, including all four designs, keyboard journeys, responsive
layouts and contrast thresholds. Edge matches the frozen Playwright configuration.
The additional CI configuration serves the production build and enables reduced
motion, avoiding development-server startup work and measurements taken during
CSS transitions. Test thresholds are unchanged. Failed frontend runs retain their
synthetic-fixture traces for five days.

The runnable prototype loads a documented selected-card contrast correction while
retaining the original entrypoint and historical source hashes. See
[snapshot and maintenance boundaries](../use_cases/Live%20Prototype%20Comparison/README.md#prototype-snapshot-and-maintenance).

Ruff lint and formatting gates cover `src`, `tests`, `examples` and `use_cases`,
including maintained example runners and the offline publication exporter.

Contributors do not register personal runners or provide model API keys. The
workflow requests only `contents: read`. Keep private release credentials and
datasets out of pull-request jobs, caches and artifacts. Any future publishing
job must have its own reviewed permissions and protected environment.

Repository administrators must enable GitHub-hosted Actions and sufficient
capacity in the destination repository. If jobs are queued, inspect that
repository's Actions status and policy; no personal host is a prerequisite.

For normal offline coding, install `.[dev]` and run `python -m pytest -q`.
The default excludes `browser`, `media` and `publication`. This does not remove
coverage from release CI; explicit `-m` selections override the default.

Run the release checks locally:

```powershell
python -m pip install -e ".[dev,live,media]"
python -m playwright install chromium
python -m ruff check --config pyproject.toml src tests examples use_cases
python -m ruff format --check --config pyproject.toml src tests examples use_cases
python -m pytest -q -m "not publication"
python -m pytest -q -m publication tests\publication
python -m build
```

To run the frontend gates from the repository root (Node.js 22 required):

```powershell
npm ci --prefix "use_cases\Live Prototype Comparison\prototype"
npm run build --prefix "use_cases\Live Prototype Comparison\prototype"
npm test --prefix "use_cases\Live Prototype Comparison\prototype"
npm run test:ui --prefix "use_cases\Live Prototype Comparison\prototype" -- --config=playwright.ci.config.ts --workers=2
```

The browser suite requires Microsoft Edge. GitHub-hosted CI installs it explicitly;
local contributors can use their existing Edge installation.
