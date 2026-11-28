# Configuring the Structured Evaluation Model

## Use Cases

There are many "have the model make a judgment" scenarios in HaijunBot, such as picking the few rules that best match the current task from a batch of candidates, scoring tracks to be installed, or judging whether a piece of logic can be replaced with an off-the-shelf Rust library.

These scenarios use the Normal model in the model group by default and rely on prompt conventions + regex parsing to get results. If you want such judgments to be more stable and more cost-efficient, or want to use a model that specializes in structured output (for example Jev / TypeSafe System One) specifically for evaluation, you can additionally configure a **structured evaluation model** in the model group.

After configuration, these decision scenarios automatically switch to that model; **when it is not configured, the behavior is exactly the same as now**, it will not error, and it will not change any default flow.

## How to Configure

The structured evaluation model is specified via the `eval_llm` reference in the model group, written exactly like `normal_llm` / `cheap_llm` / `smart_llm`.

### 1. Define the evaluation model in `llms`

```json
{
  "llms": {
    "my_normal": {
      "platform": "openai",
      "model": "gpt-5"
    },
    "my_eval": {
      "platform": "jev",
      "model": "systemone",
      "max_input_token_count": 200000,
      "llm_config": {
        "typesafe_api_key": "your API key"
      }
    }
  }
}
```

### 2. Reference it in the model group

```json
{
  "llm_group": "default",
  "llm_groups": {
    "default": {
      "normal_llm": "my_normal",
      "eval_llm": "my_eval"
    }
  }
}
```

Key points:

- `eval_llm` is **optional**; if it is not written, the structured evaluation model is not enabled.
- Leaving an empty string (`""`) is equivalent to not configuring it.
- Like other references, the value of `eval_llm` must be a name that already exists in `llms`; otherwise, an error occurs at startup.
- Like `normal_llm` and others, you **cannot** write `eval_platform` / `eval_model` / `eval_max_input_token_count` directly in `llm_groups`; you can only reference them via `eval_llm`.

## Behavior When Not Configured

When `eval_llm` is not configured:

- All decision scenarios continue along their own original flows (usually the Normal model).
- No additional model instances are created, and there is no extra overhead.
- Existing `normal_llm` / `cheap_llm` / `smart_llm` configurations are unaffected.

## Behavior After Configuration

When `eval_llm` is configured:

- Decision scenarios give priority to the evaluation model.
- If the evaluation model call fails, returns empty, or returns content that cannot be parsed into the expected format, the system **automatically falls back** to the original flow and gives a `⚠️` prompt in the terminal, without interrupting the task.

## Prompts and Feedback You Will See

- On fallback you will see something like: `⚠️  Structured evaluation model call failed, falling back to the existing flow: ...`
- When not configured, there is no related prompt, consistent with the previous experience.

## FAQ

**Q: After configuration, will the Normal model still be used?**

Yes. The evaluation model only takes over the "make a judgment" scenarios; main conversation, code generation, and so on still use the Normal / Smart model.

**Q: Can the evaluation model be the same model as Normal?**

Yes. `eval_llm` can reference any defined LLM configuration, including one that points to the same target as `normal_llm`.

**Q: What happens if the evaluation model returns the wrong format?**

The system falls back to the original flow and the task continues; this judgment just did not use the evaluation model.
