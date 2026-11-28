# Talking Directly to the Current Model

## Use Cases

When you want to first verify on its own whether the platform and model corresponding to the current model group respond normally, or just want to quickly try a few chat rounds to confirm the connection, output content, and reply style are normal, you can directly enter this platform chat mode.

## Steps

1. Type the following command in the terminal, then press Enter: `hpm chat`
2. If you want this time to temporarily use a different model group, you can instead use a command like: `hpm chat --llm-group <your-model-group-name>`. If not specified, the system uses the current default model group.
3. After startup, the system first checks whether the current platform and model are available.
4. After the connection succeeds, you enter the multiline input area.
5. Enter your question or instruction in the input area, then submit it using the submit method prompted by the current terminal.
6. After the system returns a reply, you can continue entering the next round of content for a continuous conversation.
7. To quit, just type `/bye` and submit.
8. If you submit empty content directly, the system also ends this chat.

## Prompts and Feedback You Will See

- On a successful connection, you see something like: `✅ Connected to <platform> platform <model> model`.
- Just after entering the chat, the system prompts that you can start typing and explains that you can quit via `/bye`.
- Each time the model returns content, the reply is displayed as a titled message block, with the current platform and model name in the title.
- If the model returns an empty result, you see a warning prompt instead of normal reply content.
- If an error occurs during the call, you see: `❌ Chat failed: ...`.
- If it fails at the initialization stage, you see: `❌ Session initialization failed: ...`.
- After entering `/bye`, you see: `✅ Goodbye!`.
- When you submit empty content, the system gives an ending prompt and exits the chat.

## Notes

- This is an interactive chat feature in the terminal, not a task execution interface for the general agent or code agent.
- It is more suitable for "checking model connectivity and response quality" rather than complex task orchestration.
- There are two ways to quit: type `/bye`, or directly submit empty content.
- If you temporarily specify a model group, this chat only takes effect for the current command and does not automatically rewrite the default config.
- If the current platform or model configuration itself is invalid, the chat will not start, and you need to fix the corresponding config first.
