# Connecting External Tools via MCP Config

## Use Cases

If you want to bring capabilities provided by external services or external processes into HaijunBot and use them as tools, you can register them via the `mcp` item in the config file. This approach is suitable for connecting MCP services you maintain yourself or MCP tool services provided by third parties.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Add or modify the `mcp` config option. It is an array, and each item represents one MCP connection config.
3. First confirm which approach the service you want to connect uses, for example:
   - Local command-launched type
   - URL-based remote service type
4. Fill in the required fields according to the service type. At minimum you need:
   - Name
   - Type
   - Whether enabled
   - The connection parameters required by that type
5. Example 1: local command-launched type

   ```yaml
   mcp:
     - name: local-mcp
       type: stdio
       enable: true
       command: python
       args:
         - /path/to/your_mcp_server.py
   ```

6. Example 2: remote service type

   ```yaml
   mcp:
     - name: remote-mcp
       type: sse
       enable: true
       base_url: http://127.0.0.1:8081/sse
   ```

7. Example 3: remote service type based on Streamable HTTP

   ```yaml
   mcp:
     - name: stream-mcp
       type: streamable
       enable: true
       base_url: https://example.com
       endpoint_path: mcp
   ```

   > `base_url` holds the service's host address, and `endpoint_path` holds the MCP endpoint path (default `mcp`); the two are concatenated into the actual request address. When you need extra request headers (such as User-Agent or Bearer authentication), specify them with the `headers` field.

8. Save the config file.
9. Restart the session so HaijunBot re-reads the MCP config.
10. After startup, check whether these external tools appear in the currently available tools.

## Prompts and Feedback You Will See

- If a particular MCP config is explicitly disabled, the system skips it directly and does not register that capability.
- If the config is missing required fields, such as a missing type, missing command, or missing address, the system gives a warning.
- If the connection succeeds and the external side returns a tool list, these tools are registered as currently available tools.
- In addition to tool calls, the system may also register resource listing and resource reading capabilities.
- If the remote side returns an empty tool list, the system gives a warning rather than pretending the connection succeeded.

## Example: Parallel Search MCP (web search without an API key)

If you want HaijunBot to search the latest web pages or read the content of a specified web page without configuring any API key, you can connect the free Search MCP officially provided by Parallel. It provides two tools:

- `web_search`: real-time web search, returning relevant results and summaries.
- `web_fetch`: extract clean Markdown content from a specified URL.

**Free and anonymous to use, no API key required** (anonymous use has a lower rate limit; for a higher rate limit, you can pass Parallel API key Bearer authentication in `headers`). Endpoint: `https://search.parallel.ai/mcp`.

Add the following config to `~/.haijunbot/config.yaml`:

```yaml
mcp:
  - name: parallel-search
    type: streamable
    enable: true
    base_url: https://search.parallel.ai
    endpoint_path: mcp
    headers:
      User-Agent: HaijunBot
```

Notes:

- `base_url` holds Parallel's host address and `endpoint_path` holds `mcp`, so the actual request is to `https://search.parallel.ai/mcp` (do not include a trailing slash; the Parallel endpoint does not accept a trailing slash).
- `headers.User-Agent` is used to identify the request source as HaijunBot and can be adjusted as needed.
- After a successful connection, the two tools `parallel-search.tool_call.web_search` and `parallel-search.tool_call.web_fetch` are registered.
- For a higher rate limit, you can apply for a Parallel API key and pass it via `headers.Authorization` (for example `Authorization: Bearer <your-key>`).

## Notes

- The config option name is `mcp`.
- Different connection types require different fields; before writing the config, first confirm which connection method the target service supports.
- If `mcp` is explicitly written in the config file, the system loads according to the config in preference to scanning the local MCP directory first.
- Even after a successful connection, these tools may still be filtered by `tool_group`, a whitelist, or a blacklist.
