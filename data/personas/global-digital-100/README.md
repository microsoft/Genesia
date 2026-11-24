# Global Digital 100: Public Synthetic Persona Pool

[Persona data notice](../../README.md) |
[100 profiles](personas.json) | [Quality summary](quality-summary.json)

One hundred clearly fictional adult Personas for qualitative research on general
digital products and software. This is the existing, owner-approved
`global-digital-100-v1` publication, **not a new generation**.

Every record is marked `synthetic_status: fictional_public_example`, is
English-capable, and has a stable ID. Identities, employers, institutions and
biographies are synthetic, not claims about real people. The repository's
[MIT license](../../../LICENSE.txt) applies to this explicitly published pool.

## Coverage, Not Population Representation

| Dimension | Exact published coverage |
|---|---|
| Age bands | 18–24: 15; 25–34: 20; 35–44: 20; 45–54: 15; 55–64: 15; 65–74: 15 |
| Gender | Woman: 45; Man: 45; Nonbinary: 10 |
| Regions | North America: 15; Latin America and Caribbean: 10; Europe: 15; Sub-Saharan Africa: 10; Middle East and North Africa: 10; South Asia: 15; East Asia: 10; Southeast Asia: 10; Oceania: 5 |
| Occupation contexts | Eleven families, including employed, student, transition, homemaking and retired contexts |
| Technical confidence | high: 34; medium: 33; low: 33 |
| Product familiarity | novice, occasional, regular, expert: 25 each |
| Device/access context | Five contexts: 20 each |
| Decision style | consultative: 34; deliberate: 33; quick: 33 |

`Nonbinary` does not mean every such Persona is agender. Demographics do not
determine technical confidence, accessibility, risk tolerance, behavior or product
preference. Use the [quality summary](quality-summary.json) for complete
distributions, anchor coverage, repetition and similarity measurements.

## Generation, Approval And Integrity

- Generation: `global-digital-100-recovered-from-v3`, sourced from the preserved
  `global-digital-100-direct-generation-v3` candidate run.
- Exactly 100 candidates were generated and individually risk-reviewed; all 100
  were selected, with zero rejected or eligible-unselected candidates.
- The recovery performed deterministic audit and selected-cohort review, not
  another Persona-generation pass.
- The approved cohort review has **low** severity: a mild template-like narrative
  tone remains despite measured behavioral coverage. Synthetic realism is not
  established by a passing structural check.
- The original complete generation and exact cohort approval were revalidated
  before this repository publication; their hash-bound provenance is in
  [publication-manifest.json](publication-manifest.json).
- Persona SHA-256:
  `439da3fb95672264c0707f3d516dbe170e7a1fc4753bc70982171dd96b5d65a4`.

The four-file publication intentionally excludes candidates, model requests,
events, raw evidence, internal plans and the managed generation directory.
It does not fabricate a second approval or claim that these public files alone
reproduce the full generation audit.

## Use The Pool

Paths inside a task resolve relative to that task file. For a task under
`use_cases/Live Prototype Comparison/`, for example:

```yaml
cohort:
  source: ../../data/personas/global-digital-100/personas.json
  size: 20
  seed: 42
```

The comparison runner can explicitly select this public pool:

```powershell
python "use_cases\Live Prototype Comparison\run.py" `
  --personas data\personas\global-digital-100\personas.json `
  --allow-model-data --preflight
```

Start your authorized same-origin A/B prototype and review all sending
permissions before a real run. A new sample is **not** the original 1022 fixed
twenty-person study. Persona aliases in published reports are not pool IDs.
Sampling fewer than 100 does not preserve the full pool's quotas.

Optional filters use full dotted profile paths, such as
`Core Identity.region: Europe`; ensure the filtered pool can meet your sample
size. Other useful fields include `age_band`, `research_segment`,
`technical_confidence`, `product_familiarity`, `device_and_access_context` and
`decision_style`.

This is a standalone **published pool**, not a managed generation directory.
`genesia personas validate` applies to the private original generation, not to
this four-file package. Do not copy only the public profiles into a managed
generation or claim that a subset preserves an approved full-cohort contract.
For a research-specific population, quota or sensitive context, create, review
and approve a new cohort rather than treating this pool as representative.
