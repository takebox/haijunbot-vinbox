# Connecting to the HaijunBot Gateway from the Browser

## Use Cases

Once you have started the Web Gateway service and want to open the HaijunBot web interface in a browser to use the Agent, message area, terminal, and editor, you need to complete the browser connection first.

## Steps

1. Open the HaijunBot Web UI in a browser.
2. The first time the page loads, the "Connect to HaijunBot" window pops up automatically.
3. In the "Gateway Address" input, enter your Web Gateway address. Valid formats include:
   - `127.0.0.1:8000`
   - `example.com:8000`
   - A full address with a protocol, e.g. `ws://example.com:8080/ws`

4. In the "Username" input, enter a username (use `admin` for the first time).
5. If password authentication is enabled on the current gateway, enter the password in the "Password" input; if not, you can leave it empty.
6. Click "Connect".
7. After connecting successfully, the connection window closes automatically and the UI enters its normal state.
8. If the connection drops later, the connection window reappears, and you can enter your information again to reconnect.

## Feedback You Will See

- When you open the page for the first time, you will see a connection dialog titled "Connect to HaijunBot".
- While connecting, the button shows "Connecting...".
- After a successful connection, the status at the top switches from "Connecting" to "Connected".
- If the connection fails, an error message appears in the connection window.
- If you enter an invalid address format, the UI directly shows "Invalid gateway address format".
- When the connection drops, the status at the top returns to not connected, and the connection dialog reappears.

## Notes

- Browser connection only makes sense when the Web Gateway is already running.
- The gateway address accepts both the shorthand and the full URL; either works, but the address and port must be reachable.
- If the current page is served over HTTPS, the UI automatically prefers the secure protocol when connecting.
- The browser remembers the last gateway address that connected successfully, so you can reuse it the next time you open the page.
