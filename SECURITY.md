<!-- BEGIN MICROSOFT SECURITY.MD V1.0.0 BLOCK -->

## Security

Microsoft takes the security of our software products and services seriously, which
includes all source code repositories in our GitHub organizations.

**Please do not report security vulnerabilities through public GitHub issues.**

For security reporting information, locations, contact information, and policies,
please review the latest guidance for Microsoft repositories at
[https://aka.ms/SECURITY.md](https://aka.ms/SECURITY.md).

<!-- END MICROSOFT SECURITY.MD BLOCK -->

## Project-Specific Data Handling

Genesia is a local research tool, not a sandbox or a hosted multi-tenant service.

- Model traffic goes to the user-configured OpenAI-compatible API. Remote endpoints require HTTPS; keys are read only from the named environment variable and are not persisted. Profile, material and screenshot sending permissions must be explicitly enabled.
- Figma access is separately controlled by `fetch_figma`. The token is read from an environment variable and sent only to the Figma API. Export URLs are constrained to HTTPS Figma/AWS domains and bounded downloads; redirects are not followed. No token value or signed image URL is persisted.
- Use disposable prototypes. Same-origin browser actions can mutate a server; origin filtering does not replace application authorization. Never use real production accounts, sensitive downloads, payments or destructive workflows.
- Source documents and personas are untrusted model context. Prompts and action schemas restrict their authority, but prompt injection cannot be eliminated by prompts alone.
- Runs contain model requests, traces, screenshots and personas. Filesystem permissions, retention and redaction are the caller's responsibility. Git ignore is not encryption or access control.
- The bundled public Persona pool is explicitly fictional. Review its publication notice, coverage and limitations; synthetic profiles are not observed human data, population estimates or permission to publish unrelated material.
- Video sampling can miss transient states. Trace timestamps must be relative seconds or an explicit relative clock; aligned clicks do not certify that a control worked.
- Evidence hashes check integrity, not truth. Model-assisted readiness/fidelity reviews are advisory and may be wrong. Findings and priority estimates require researcher review.
- The budget ledger bounds requests and estimates token reservation; it is not a guaranteed provider billing limit. Input file size limits do not make arbitrary malicious media safe to decode. Keep native media parsers patched and isolate untrusted media when needed.

For a suspected vulnerability, use the Microsoft reporting guidance above. Do not post tokens or
private study artifacts in public issues.
