# Quickly Configuring the OpenAI or Haijun Platform

## Use Cases

When you first connect HaijunBot, or want to quickly write a new OpenAI / Haijun platform configuration into the local config file, you can use this interactive quick-configuration flow. It suits people who do not want to edit the config file by hand and prefer the system to prompt for input step by step.

## Steps

1. Type the following command in the terminal, then press Enter: `hqc`
2. After the command starts, it immediately enters the interactive flow and prompts you in order:
   - Platform type: only `haijun` or `openai` is supported
   - API base URL
   - API key
3. The system tries to read the available models.
   - If the model list is obtained successfully, you first see a list of selectable models.
   - If multiple models are currently obtained, the system first asks whether you want to configure all models at once.
4. If you do not want to configure all of them, enter the model numbers as prompted. Multiple models can be separated by commas.
5. If the model list does not contain the model you want, or the model list was not obtained successfully at all:
   - The system lets you switch to manually entering model names.
   - At this point you can directly enter one or more model names, separating multiple models with commas.
6. After the models to configure this time are selected, the system continues by having you choose three role models for this model group:
   - Normal: used for most ordinary scenarios
   - Smart: more oriented toward complex tasks or code generation
   - Cheap: more oriented toward low-demand, high-volume scenarios
7. If the original local config file already has other models, the system may also first ask you whether to also allow selecting Normal / Smart / Cheap from the models in the existing config.
8. After the models are chosen, the system first tests whether the Normal model you selected can connect to the current API.
9. If the connectivity test fails, the system continues by asking whether you still want to save the configuration:
   - If you choose not to save, the flow ends directly.
   - If you choose to continue, the system still proceeds and writes the config.
10. Next, enter the model group name as prompted; if you press Enter directly, the system uses a default name automatically generated based on the Normal model.
11. Then the system asks one by one for the max token count of each model actually used this time:
    - When pressing Enter directly, the default or existing value is used.
    - If the same model is reused by multiple roles, the system asks only once.
12. After everything is done, the system:
    - Reuses existing identical model configurations, or creates configurations for new models
    - Creates a model group
    - Sets this model group as the current default model group
    - Saves the result to `~/.haijunbot/config.yaml`

## Prompts and Feedback You Will See

- At the beginning you see a prompt like: `🚀 Starting to configure the OPENAI platform` or `🚀 Starting to configure the HAIJUN platform`.
- If the platform type is not `haijun` or `openai`, the system directly prompts that the platform is unsupported and ends.
- After successfully obtaining the models, you see an available-model summary and a model list numbered by index.
- If obtaining the model list fails, you see a failure prompt, then a confirmation asking "whether to manually enter model names".
- When you finish selecting models, you see: `✅ Selected X models: ...`.
- When choosing Normal / Smart / Cheap, the system lists candidate models item by item and asks you to enter an index.
- After selecting, you see something like:
  - `🎯 Normal model: ...`
  - `🧠 Smart model: ...`
  - `💰 Cheap model: ...`
- During the connectivity test, you see: `🔍 Testing model ... API connectivity...`.
- When the test passes, you see: `✅ API connectivity test passed`.
- When the test fails, you see the specific failure reason, and it continues by asking whether you still want to save the configuration.
- After saving successfully, you see these kinds of result prompts:
  - Reused existing model configurations, or created configurations for some models
  - Created a model group
  - Set the default model group
  - `✅ Configuration saved to ~/.haijunbot/config.yaml`

## Notes

- This flow explicitly supports only the two platform types `haijun` and `openai`.
- This is a pure terminal interactive flow and does not open a browser page.
- OpenAI-style platforms try to read an online model list; Haijun-style flows directly provide a set of known model candidates, so the "available model list" is not necessarily exactly all the models under your account.
- If the model list is not obtained successfully, you can still manually enter model names to continue configuring.
- A connectivity test failure does not forcibly prevent saving; if you choose to continue saving, actually using that model later may still fail.
- If a configuration for the same model already exists locally, the system may directly reuse the original configuration rather than creating a duplicate new one.
- What is written here is persistent config and will rewrite the current default model group; it is not the same as temporarily switching the model group within a session.

## Non-Interactive Quick Configuration (convenient for CI / automation)

The interactive flow above suits manual configuration; if you need to complete configuration in CI or a script without human input, you can use either of the following two approaches.

### Option A: Environment variable override (takes effect at runtime, does not write config)

When reading config, HaijunBot supports overriding the platform and model with environment variables, with the priority **environment variables > config.yaml > defaults**. This approach does not rewrite `~/.haijunbot/config.yaml` and only takes effect for the current run, making it suitable for temporarily specifying a model in CI.

| Environment variable | Purpose                                        | Default value    |
| -------------------- | ---------------------------------------------- | ---------------- |
| `OPENAI_API_KEY`     | OpenAI platform API key                        | None             |
| `JUGLOW_API_KEY`  | Haijun platform API key                        | None             |
| `OPENAI_API_BASE`    | API base URL                                   | Platform default |
| `HAIJUNBOT_MODEL`       | Override the model name                        | `gpt-5`          |
| `HAIJUNBOT_PLATFORM`    | Override the platform type (`openai`/`haijun`) | `openai`         |

Example:

```bash
export OPENAI_API_KEY=sk-xxx
export HAIJUNBOT_MODEL=gpt-4o
export HAIJUNBOT_PLATFORM=openai
hjb -n --task "your task"
```

> The first run of `hjb` automatically generates a default `~/.haijunbot/config.yaml` (no interaction); the API Key is injected via the standard environment variables above, with no need for a preset config file.

### Option B: `hqc` non-interactive mode (persistently writes to config.yaml)

`hqc` supports a non-interactive mode with parameters, directly writing the config into `~/.haijunbot/config.yaml`, suitable for preparing persistent config in advance in CI.

```bash
hqc --platform openai \
    --base-url https://api.openai.com/v1 \
    --api-key sk-xxx \
    --model gpt-4o \
    --group default \
    --skip-test
```

Non-interactive parameter descriptions:

| Parameter      | Required | Description                                                   |
| -------------- | -------- | ------------------------------------------------------------- |
| `--platform`   | Yes      | Platform type (`openai`/`haijun`)                             |
| `--base-url`   | Yes      | API base URL                                                  |
| `--api-key`    | Yes      | API key                                                       |
| `--model`      | Yes      | Model name (shared by normal/smart/cheap)                     |
| `--group`      | No       | Model group name; defaults to the model name                  |
| `--max-tokens` | No       | Maximum input token count, default `200000`                   |
| `--skip-test`  | No       | Skip the API connectivity test (recommended for CI scenarios) |

> Interactive mode: just run `hqc` (without parameters) and enter input as prompted; the logic remains unchanged.
