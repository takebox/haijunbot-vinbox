# Starting an OpenAI-Compatible API Service

## Use Cases

When you want to expose the platform and model HaijunBot currently uses by default in the form of an OpenAI-compatible interface for other programs, scripts, or callers to access, you can start this service.

## Steps

1. First confirm that the platform and model corresponding to your current default model group already work normally.
2. Type the following command in the terminal, then press Enter: `hpm service`
3. If you do not pass extra parameters, the system uses the default host address `127.0.0.1` and default port `8000`.
4. If you want to change to another listening address or port, you can use a command like: `hpm service --host 0.0.0.0 --port 9000`
5. After submitting, the system reads the current default platform and default model, and starts the OpenAI-compatible API service using them as the service's default backend.
6. After the service starts, just have your external program access it at this address.
7. When you are done, stop the service by interrupting it in the current terminal.

## Prompts and Feedback You Will See

- If it starts successfully, the current terminal enters a continuously running state, indicating the service has begun listening.
- By default, the listening address is `127.0.0.1:8000`.
- If you change the host or port, the subsequent access address changes accordingly.
- If the current default platform or model configuration is incomplete, or the underlying service fails to start, you see the corresponding error or exception prompt rather than entering the normal listening state.

## Notes

- This service depends on your current default platform and model configuration working properly, so it is best to first confirm the default model group has been fully configured, and if necessary use "Viewing Current Platform and Model Info" or "Talking Directly to the Current Model" to check.
- When no parameters are passed, it only listens on `127.0.0.1:8000`, which is usually suitable only for local access.
- If you want to change the host address and port, pass them in together at startup.
- This is a continuously running service process; unlike an ordinary query operation, it does not exit immediately after completing.
- What is started here is the OpenAI-compatible interface service, not the Web config page.
