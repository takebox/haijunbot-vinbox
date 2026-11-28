# Logging into the Web Gateway with a Password

## Use Cases

HaijunBot Web Gateway uses a **username + password** account system for authentication. When connecting, you first enter the username and password in the web page to obtain an access credential, and only then can you access the Agent list, files, terminal, and other web features normally.

## Steps

1. First make sure you have an account that can log in (the first startup creates the `admin` account automatically; the initial password comes from the environment variable `HAIJUNBOT_ADMIN_PASSWORD`, see "Configuring the Gateway Authentication Password and the Access Policy When No Password Is Set" for details).
2. Open the Web UI in a browser and enter the "Connect to HaijunBot" window.
3. In the "Username" input, enter the username (use `admin` for the first time).
4. In the "Password" input, enter the correct password.
5. In the "Gateway Address" input, enter the Web Gateway address.
6. Click "Connect".
7. The page logs in with the username and password you entered first, then continues to establish the connection.
8. After a successful login, the page enters the connected state and you can keep using the other web features.

## Feedback You Will See

- If login succeeds, the page continues the connection flow and closes the connection dialog automatically.
- After a successful login, the content in the password input is cleared automatically.
- If the username or password is wrong or login fails, the connection window shows the failure reason instead of entering the connected state.
- After a successful login, subsequent API calls and connections automatically carry the current access credential.

## Notes

- This password is not re-entered on every send operation; you log in once before connecting.
- After a successful login, the access credential is only kept while the current page session is running; if you refresh or reopen the page, you usually need to log in again.
- The default username is `admin`; if you created other users under "Management → User Management", you can log in with the corresponding username as well.
- If you have already connected but the credential later expires or the gateway restarts, the page may return to the connection dialog and require another login.
