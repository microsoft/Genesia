# Use Cases

Authored examples consume the public Genesia SDK without adding product-specific
behavior to the core runtime.

| Example | Purpose | Entry |
|---|---|---|
| [Live Prototype Comparison](Live%20Prototype%20Comparison/README.md) | Twenty-Persona A→B exploration and interview, with [sample reports and twenty complete GIFs](Live%20Prototype%20Comparison/sample/README.md) | [run.py](Live%20Prototype%20Comparison/run.py) |
| [Specification & Screenshot Review](Specification%20%26%20Screenshot%20Review/README.md) | Build an environment from a spec and still images, then run Persona review, interview and insight analysis; [completed 20-Persona sample](Specification%20%26%20Screenshot%20Review/sample/README.md) | [run.py](Specification%20%26%20Screenshot%20Review/run.py) |
| [Profile-Grounded Persona Survey](Profile-Grounded%20Persona%20Survey/README.md) | Explore hypothetical task fit and confirmation boundaries using profile-grounded questions, conditional branches and descriptive statistics; [completed 20-Persona sample](Profile-Grounded%20Persona%20Survey/sample/README.md) | [run.py](Profile-Grounded%20Persona%20Survey/run.py) |

The comparison case includes its frozen prototype source and a
[`--local-prototype` workflow](Live%20Prototype%20Comparison/README.md#run-the-bundled-case):
after setup, Persona Agents operate both designs and generate a new insight report.
Alternatively, independently serve your own isolated same-origin prototype.
Supply an authorized Persona source; the [public synthetic pool](../data/README.md)
is an explicitly fictional option. Configure your API endpoint, model and key
environment variable before network preflight; no example starts inference or sends data silently.

Reviewed publications live in `sample/`. Raw runs and unreviewed outputs belong
under ignored `runs/` or `local/`; they are not part of source distributions.
Folder names use the display titles above. Quote paths in shell commands, as the
names contain spaces and one contains `&`. Historical `case` identifiers inside
saved publication manifests retain their original values; moving a case does
not rewrite its evidence or its source hashes.

The current samples use the V3 answer-stage policy: Sol at temperature 1 for the
live comparison's new final interview and the full specification/screenshots study,
and Terra at temperature 1 for the complete profile survey. The live sample retains
all twenty original journey GIFs. The specification/screenshots case includes its source material;
the survey includes the complete questionnaire and descriptive distributions.
The live comparison retains its twenty-question protocol and one current native report.
Each case remains configurable for a caller-authorized OpenAI-compatible endpoint
and model. Sample models, settings, coverage and limitations are recorded in its
manifest; source integrity is not proof of Persona realism or product outcomes.
