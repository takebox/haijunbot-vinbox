# Launching the Web Config UI to Edit Config

## Use Cases

When you do not want to write the config file by hand but instead want to edit HaijunBot config through a visual page in the browser, you can launch this Web config UI.

## Steps

1. Type the following command in the terminal, then press Enter: `hcfg`
2. If you do not specify extra parameters, the system defaults to:
   - Using the built-in config Schema
   - Setting the output file to `~/.haijunbot/config.yaml`
   - Starting the service on port `8080`
   - Automatically trying to open the browser after startup
3. If you need to use a different Schema file, you can specify an extra Schema path at startup, for example: `hcfg --schema /your/schema.json`
4. If you want to save the result to a different file, you can also specify the output file path at startup, for example: `hcfg --output /your/config.yaml`
5. If you need to change the port, you can specify the port number at startup, for example: `hcfg --port 3000`
6. If you do not want the system to open the browser automatically, add `--no-browser` at startup, for example: `hcfg --no-browser`
7. After the command starts, the terminal displays the access address.
8. After opening the corresponding address in the browser, edit the config and save it following the on-page prompts.
9. When you are done, go back to the terminal that started the service and press `Ctrl+C` to stop it.

## Prompts and Feedback You Will See

- At startup, you first see a block of startup information, including:
  - `Schema file: ...`
  - `Output file: ...`
  - `Service port: ...`
- If the Schema loads successfully, you will see: `✓ Schema loaded successfully: ...`.
- If the Schema fails to load, the system reports an error and exits directly.
- If the output directory cannot be created, you will see an error prompt "cannot create output directory".
- If creating the Web app fails, it also directly prompts "failed to create app".
- After the service starts successfully, you will see:
  - `✓ Service started!`
  - The access address, for example `http://localhost:8080`
  - `Press Ctrl+C to stop the service`
- If the system successfully opens the browser automatically, you will see: `Browser opened automatically...`.
- If the automatic open fails, the system prompts you to visit the corresponding address manually.
- When stopping the service, the terminal displays: `⚠ Service stopped`.

## Notes

- This is a "terminal launch + browser editing" approach, not a pure terminal interactive flow.
- The default output file is `~/.haijunbot/config.yaml`, so the result you save through the web page is written directly into this config.
- The default access prompt shows `http://localhost:port`, but the service actually starts on a listening address that accepts external access; if you use it only on the local machine, just open the address given by the terminal.
- If you use a custom Schema or custom output file, you must explicitly pass the corresponding parameters at startup.
- After the service starts, it keeps occupying the current terminal until you press `Ctrl+C` to stop it.
