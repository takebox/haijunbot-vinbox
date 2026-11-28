# Connecting the Jev (TypeSafe System One) Platform

## Use Cases

If you want to hand off judgments like "typed decisions" to Jev — for example picking one from a batch of candidates, scoring on a scale, or making a yes/no determination — you can enable the built-in `jev` platform. Jev does not generate free text, does not support multimodality, and has no conversation history; a single request returns a structured probabilistic answer, making it suitable for replacing the "use a large model for small judgments" scenario.

## Prerequisites

- A TypeSafe API Key (created in the [TypeSafe console](https://console.typesafe.ai/)).
- Network access to `https://api.typesafe.ai` (or a compatible gateway you have built yourself).

## Steps

1. Add a new Jev model definition in `llms` in `config.yaml`, with `platform` set to `jev`:

   ```yaml
   llms:
     jev:
       platform: jev
       model: jev-latest
       max_input_token_count: 64000
       llm_config:
         typesafe_api_key: "your-typesafe-api-key"
         typesafe_api_base: "https://api.typesafe.ai"
   ```

2. Reference it in `llm_groups`. Jev is suitable for the `cheap_llm` position (used for cheap small judgments):

   ```yaml
   llm_groups:
     default:
       normal_llm: gpt-5
       cheap_llm: jev
   ```

3. Restart HaijunBot, and the platform is automatically discovered and registered during startup.

## Input Format

The Jev platform's `chat()` uses a JSON text protocol, and the input looks like:

```json
{
  "state": "the content to evaluate; can be a string, object, or array",
  "questions": {
    "is_urgent": { "type": "noul", "instructions": "Does it express urgency?" },
    "department": {
      "type": "choice",
      "instructions": "Which team should handle it?",
      "criteria": { "billing": "billing", "technical": "technical" }
    },
    "frustration": {
      "type": "score",
      "instructions": "How dissatisfied is the customer?",
      "criteria": ["calm", "dissatisfied", "very angry"]
    }
  }
}
```

There are three question types:

- `noul`: yes/no judgment, returning the probability of "yes" (0~1).
- `choice`: pick one from the options defined by `criteria`, up to 255 items, returning the selected item, the probability distribution, and confidence.
- `score`: score on the ordered scale defined by `criteria`, 2~10 levels, returning the score, the probability of each level, and confidence.

## Output You Will See

The platform serializes the structured answer into readable text, including each question's value, confidence, and probability distribution (score also includes a legend), as well as the token usage of this request.

## Notes

- **Text input only**: images, audio, and video are not supported; multimodal content is downgraded to text.
- **No conversation semantics**: Jev does not maintain context; each request depends only on the current input; `set_system_prompt` is only recorded and does not participate in requests.
- **Chinese performs worse than English**: the official documentation explicitly states that CJK support is not as good as English; before actual use, self-test with Chinese samples and pay attention to confidence.
- **Data leaving the region**: Jev is an overseas-hosted API, and the `state` content is sent to the TypeSafe server. If your content is sensitive, do a compliance assessment first.
- **Rate limiting**: on 429/529, the platform automatically retries with exponential backoff (up to 4 times) and respects the `retry-after` header.
- **Model name**: model names that do not start with `jev` are automatically fallen back to `jev-latest`, to avoid mixing in model names from other platforms.
