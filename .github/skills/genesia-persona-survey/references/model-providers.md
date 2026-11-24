# Model Configuration

Use your own OpenAI-compatible API. The endpoint and model are explicit; no model or provider fallback occurs.

```yaml
model:
  provider: openai_compatible
  base_url: https://api.openai.com/v1
  model: YOUR_MODEL_ID
  api_key_env: OPENAI_API_KEY
  timeout_seconds: 150
  max_tokens: 5000
  token_limit_field: max_completion_tokens
  attempts: 3
```

Keep the key outside YAML and source control:

```powershell
$env:OPENAI_API_KEY = "YOUR_API_KEY"
$env:GENESIA_MODEL = "YOUR_MODEL_ID"
python -m genesia preflight task.yaml --network
python -m genesia run task.yaml
```

For another compatible service, change `base_url` and, if needed, `api_key_env`.
`init` and the Persona planning/generation CLI accept `--base-url` and
`--api-key-env`; `OPENAI_BASE_URL` can supply the endpoint. These commands never
ask you to paste the secret into a saved task.

Remote endpoints require HTTPS and a key environment-variable name. Local
OpenAI-compatible services may use HTTP; set `api_key_env: null` in their task
configuration if they do not require authentication. Genesia uses `/models` and
`/chat/completions` relative to `base_url`; not every provider's native API is compatible.
Use `token_limit_field: max_tokens` if required by your compatible service.

Live and recorded research require a model that accepts image input. Verify that
capability independently: standard model catalogs do not consistently advertise it.
Profile-only surveys do not send screenshots. Profile/material/image sending
permissions remain explicit, independent of API authentication.
