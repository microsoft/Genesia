# Contributing to Genesia

This project welcomes contributions and suggestions. Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit
[Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a
CLA and decorate the pull request appropriately (for example, with a status check or comment).
Follow the instructions provided by the bot. You will only need to do this once across all
repositories using the Microsoft CLA.

This project has adopted the
[Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more
information, see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with questions or concerns.

Do not report security vulnerabilities in a public issue. Follow the instructions in
[SECURITY.md](SECURITY.md) instead.

## Issues and Feature Requests

Search existing issues before opening a new one. Bug reports should include the affected version,
operating system, expected and actual behavior, complete reproduction steps and a minimal example
when possible. Remove tokens, private Persona data, screenshots, recordings and generated research
reports before posting.

For a substantial feature or behavioral change, open an issue describing the motivation, proposed
scope and compatibility impact before starting implementation. Small fixes and documentation
improvements may be submitted directly as pull requests.

## Development Setup

Python 3.11+ is required. For normal offline SDK development, install `.[dev]`.
Default tests use scripted gateways and temporary fixtures; they do not need API
keys, Chromium, video decoders or the published GIF package.

```text
python -m ruff check --config pyproject.toml src tests examples use_cases
python -m ruff format --check --config pyproject.toml src tests examples use_cases
python -m pytest -q
python -m build
```

Browser, optional-media and repository-publication tests are explicit groups:

```powershell
python -m pip install -e ".[dev,live,media]"
python -m playwright install chromium
python -m pytest -q -m "not publication"
python -m pytest -q -m publication tests\publication
```

Use `-m browser` or `-m media` to run just one optional group. A command-line
`-m` replaces the default selection in the project configuration. Publication
audits require a full Git checkout; they are excluded from source distributions,
along with the large sample media. Functional exporter/privacy tests stay in the
default SDK suite and create their own small fixtures.

## Pull Requests

Create a focused branch, add or update tests and documentation for changed behavior, and keep the
pull request limited to one coherent change. In the pull request description:

- explain the problem and the chosen solution;
- link related issues;
- describe user-visible, schema or compatibility changes;
- list the validation commands that you ran; and
- identify any data, security or privacy implications.

Pull-request CI uses GitHub-hosted Windows runners. Contributors do not need to install
or register a runner. It also checks maintained example scripts and runs the full
frontend browser suite. See [CI configuration](docs/ci.md) for the test matrix and maintenance boundaries.

## Coding and Testing Conventions

Tests must not call paid models or external research services. Use fake gateways
and temporary fixtures. Mark real browser and optional decoder integrations with
`browser` or `media`; mark full-checkout asset audits with `publication`. Keep
schema, permission, budget, evidence and failure regressions in the default suite.
Test Skill metadata, links and executable templates rather than exact prose.
For release validation, install all extras and explicitly run all groups. New
adapters need success, invalid-input, permission, lineage and failure-cleanup tests.

Preserve persona identity, the research phase gate, current-observation authorization and evidence ownership. Do not silently replace an unavailable model, discard invalid responses, repair research results without lineage, or convert self-reported completion into a product-success assertion.

Private acceptance assets belong under ignored `local/` or an access-controlled external directory. Do
not submit additional Persona datasets, real screenshots, tokens, signed export URLs, raw recordings or
generated private reports. The published fictional pool under `data/` is an explicitly documented exception;
its inclusion does not authorize unrelated data. Tests may create minimal structural fixtures in temporary
directories, but those fixtures are not research Persona examples.

Follow the existing type annotations and module structure. Ruff defines the formatting and lint rules;
avoid unrelated formatting or generated-artifact changes. Maintainers review contributions for
correctness, tests, evidence lineage, privacy, dependency provenance and license compatibility.

Use English identifiers, comments, docstrings, error messages and fixed interface text. The default
source-language test covers Python and frontend/script sources under `.github/`, `src/`, `tests/`,
`examples/` and `use_cases/`, as well as packaged Markdown policies. Use explicit Unicode escapes for
multilingual test fixtures; do not remove support for non-English research inputs or original answers.
Seven localized files in the frozen comparison prototype are explicit, hash-checked exceptions.
Published research artifacts, private outputs and dependency/build directories are not source text.
Do not edit a frozen example merely to change its language or formatting.

Add argument and return annotations to new or changed public interfaces. Keep orchestration and
rendering changes focused, extracting cohesive helpers when needed rather than mixing a large
refactor into an unrelated fix. The current Ruff configuration does not enforce full type checking
or complexity limits; passing lint is not a substitute for review or behavioral tests.

## Project Direction

The current scope and known future work are documented in the README's
[Limits and Data Safety](README.md#limits-and-data-safety) and
[Development and Architecture](README.md#development-and-architecture) sections. Discuss roadmap
changes in an issue before implementing them.
