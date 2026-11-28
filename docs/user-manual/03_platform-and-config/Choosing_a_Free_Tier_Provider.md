# Choosing a Free-Tier Provider

HaijunBot ships every LLM lane through one OpenAI-compatible platform:
`platform: free`. The provider id decides the base URL, the environment
variable that carries the key, and the default models. Paid subscriptions
(OpenAI, Anthropic, Google) exist in the same catalog but are optional and are
never tried before a free lane.

## 1. Pick a provider

| Provider | Tier | Env key | Get a key |
|----------|------|---------|-----------|
| `openrouter` | free | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| `groq` | free | `GROQ_API_KEY` | https://console.groq.com/keys |
| `together` | free | `TOGETHER_API_KEY` | https://api.together.ai/settings/api-keys |
| `huggingface` | free | `HF_TOKEN` | https://huggingface.co/settings/tokens |
| `gemini` | free | `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `9router` | free | `NINE_ROUTER_API_KEY` | self-hosted, set `OPENAI_API_BASE` equivalent |
| `omniroute` | free | `OMNIROUTE_API_KEY` | self-hosted, set `OPENAI_API_BASE` equivalent |
| `opencode` | free | none (base URL only) | local gateway, no paid key |
| `freebuff` | free | `FREEBUFF_API_KEY` | https://freebuff.com/account/api |
| `openai` | paid | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `anthropic` | paid | `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys |
| `google` | paid | `GOOGLE_API_KEY` | https://aistudio.google.com/apikey |

`anthropic` expects an OpenAI-compatible gateway: Anthropic's native API is not
OpenAI-shaped, so set `llm_config.openai_api_base` to the gateway URL.

## 2. Start from the template

```bash
cp config.example.yaml ~/.haijunbot/config.yaml
```

The template already contains one `llms` entry per provider (`groq-free`,
`hf-free`, `openai-paid`, …) and three groups:

- `free-first` — the lane HaijunBot uses by default.
- `free-backup` — reached only when the first free lane keeps failing.
- `paid-optional` — delete this group to run free tier only.

To switch providers, point `llm_groups.free-first.normal_llm` at another
`*-free` entry, for example `gemini-free`.

## 3. Give it a valid key (providers that have one)

Either paste the key into the entry:

```yaml
llms:
  groq-free:
    platform: free
    model: llama-3.3-70b-versatile
    llm_config:
      provider: groq
      openai_api_key: "gsk_your_key_here"
```

or export the provider's environment variable and leave `openai_api_key` empty:

```bash
export GROQ_API_KEY=gsk_your_key_here
```

A key stored in `llm_config.openai_api_key` wins over the environment variable.
If neither is present HaijunBot keeps running on the local `vinbox` lane and
says so; it never pretends a paid key exists.

`opencode` is the exception: it is a local OpenAI-compatible gateway with no
key at all. Leave `openai_api_key` empty and set only the base URL:

```yaml
llms:
  opencode-free:
    platform: free
    model: opencode/default
    llm_config:
      provider: opencode
      openai_api_base: "http://127.0.0.1:4096/v1"
      openai_api_key: ""            # not used by opencode
```

## 4. Or let the wizard write it

```bash
hqc
```

The wizard prints the provider table and asks for a provider id, then:

- provider **with a key** (groq, openrouter, together, huggingface, gemini,
  freebuff, 9router, omniroute, openai, anthropic, google) — the base URL is
  filled from the catalog and the key is requested; an empty key cancels the
  configuration.
- provider **without a key** (`opencode`) — only the base URL is requested. The
  key prompt is skipped entirely and the configuration continues.

The same holds non-interactively: `hqc --platform groq --api-key ... --model ...`
for keyed providers, and `--api-key` is optional for keyless ones:

```bash
hqc --platform opencode --base-url http://127.0.0.1:4096/v1 --model opencode/default
```

The web config UI (`hqc web`) offers the same provider list through the
`provider` field in `config_schema.json`.

## 5. Check the lane

```bash
python - <<'PY'
from haijunbot.haijunbot_utils import config as cfg
print(cfg.get_normal_platform_name(), cfg.get_normal_model_name())
print(cfg.get_llm_config("normal"))
PY
```

A healthy free-tier lane prints `free` as the platform and a base URL such as
`https://api.groq.com/openai/v1`.

## Troubleshooting

- `no API key yet` — paste the key or export the env variable listed above.
  This never appears for `opencode`, which needs no key.
- `base URL is empty` — only `9router`, `omniroute`, `opencode` and `anthropic`
  have no default; set `llm_config.openai_api_base`. For `opencode` the base URL
  is the only required field, so the wizard and `hqc --base-url` ask for exactly
  that and nothing else.
- `401` / `403` after switching — the key belongs to another provider; check
  that `provider` matches the key.
