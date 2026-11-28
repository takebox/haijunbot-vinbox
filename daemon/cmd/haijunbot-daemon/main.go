// Command haijunbot-daemon is the HaijunBot local daemon.
//
// Responsibility: receive login info pushed from the web page, connect to the gateway using the same protocol as the browser extension,
// stay online and receive commands (command handling is a placeholder implementation).
//
// Usage:
//
//	haijunbot-daemon run                 run in the foreground (default behavior)
//	haijunbot-daemon install             install as a system service and enable auto-start on boot
//	haijunbot-daemon uninstall           stop and uninstall the system service
//	haijunbot-daemon start|stop|restart  service lifecycle management
//	haijunbot-daemon status              view service status
package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	"haijunbot-daemon/internal/auth"
	"haijunbot-daemon/internal/capability"
	"haijunbot-daemon/internal/config"
	"haijunbot-daemon/internal/daemonlog"
	"haijunbot-daemon/internal/gatewayfilter"
	"haijunbot-daemon/internal/jsruntime"
	"haijunbot-daemon/internal/localapi"
	"haijunbot-daemon/internal/login"
	"haijunbot-daemon/internal/proxy"
	"haijunbot-daemon/internal/selfupdate"
	"haijunbot-daemon/internal/service"
	"haijunbot-daemon/internal/webui"
	"haijunbot-daemon/internal/wsclient"
)

// version is the daemon version, reported to the gateway as extension_version.
//
// Declared as var rather than const so the real version can be injected via build flags at release time:
//
//	go build -ldflags "-X main.version=v5.0.5" ./cmd/haijunbot-daemon
//
// The default below is used when not injected.
var version = "0.1.0"

// currentStore is the credential store created by runDaemon, used by the auto-update flow to temporarily persist credentials before updating.
// It is only assigned within runDaemon; the subcommand paths do not use it.
var currentStore *auth.Store

// currentManager is the multi-gateway connection manager created by runDaemon, used by the auto-update flow to report progress
// (daemon.update.status). It is only assigned within runDaemon; the subcommand paths do not use it.
var currentManager *wsclient.Manager

func main() {
	if len(os.Args) > 1 && !isFlag(os.Args[1]) {
		if err := runSubcommand(os.Args[1], os.Args[2:]); err != nil {
			log.Fatalf("[daemon] %v", err)
		}
		return
	}
	runDaemon(os.Args[1:])
}

// isFlag reports whether the argument is an option (starts with '-').
func isFlag(arg string) bool {
	return len(arg) > 0 && arg[0] == '-'
}

// runSubcommand dispatches service management subcommands.
func runSubcommand(name string, args []string) error {
	switch name {
	case "run":
		runDaemon(args)
		return nil
	case "install":
		return cmdInstall(args)
	case "uninstall":
		return cmdSimple("uninstall", func(s service.Service) (string, error) { return s.Uninstall() })
	case "start":
		return cmdSimple("start", func(s service.Service) (string, error) { return s.Start() })
	case "stop":
		return cmdSimple("stop", func(s service.Service) (string, error) { return s.Stop() })
	case "restart":
		return cmdSimple("restart", func(s service.Service) (string, error) { return s.Restart() })
	case "status":
		return cmdStatus()
	case "self-update-apply":
		return cmdSelfUpdateApply(args)
	case "login":
		return cmdLogin(args)
	case "gateway-filter":
		return cmdGatewayFilter(args)
	case "run-script":
		return cmdRunScript(args)
	case "help", "-h", "--help":
		printUsage()
		return nil
	default:
		printUsage()
		return fmt.Errorf("unknown subcommand: %s", name)
	}
}

// cmdInstall installs the service: writes the service definition and enables auto-start on boot (without starting).
func cmdInstall(args []string) error {
	fs := flag.NewFlagSet("install", flag.ContinueOnError)
	listenFlag := fs.String("listen", "", "local API listen address (overrides config file)")
	gatewayFlag := fs.String("gateway", "", "default gateway address (overrides config file)")
	configFlag := fs.String("config", "", "config file path (default ~/.haijunbot/daemon/config.yaml)")
	if err := fs.Parse(args); err != nil {
		return err
	}

	opts := service.Options{
		Listen:     *listenFlag,
		Gateway:    *gatewayFlag,
		ConfigPath: *configFlag,
	}
	if notice := service.InstallNotice(); notice != "" {
		fmt.Printf("[daemon] %s\n", notice)
	}
	msg, err := service.New().Install(opts)
	if err != nil {
		return err
	}
	fmt.Printf("[daemon] %s\n", msg)
	if hint := service.StartHint(); hint != "" {
		fmt.Printf("[daemon] %s\n", hint)
	} else {
		fmt.Println("[daemon] Tip: use haijunbot-daemon start to start the service")
	}
	return nil
}

// cmdSimple executes a parameterless service operation and prints the result.
func cmdSimple(action string, fn func(service.Service) (string, error)) error {
	msg, err := fn(service.New())
	if err != nil {
		return fmt.Errorf("%s service failed: %w", action, err)
	}
	fmt.Printf("[daemon] %s\n", msg)
	return nil
}

// cmdStatus queries and prints the service status.
func cmdStatus() error {
	st, err := service.New().Status()
	if err != nil {
		return fmt.Errorf("failed to query service status: %w", err)
	}
	fmt.Printf("[daemon] Running: %v\n", st.Running)
	fmt.Printf("[daemon] Auto-start on boot: %v\n", st.Enabled)
	if st.PID > 0 {
		fmt.Printf("[daemon] PID: %d\n", st.PID)
	}
	if st.Detail != "" {
		fmt.Printf("[daemon] Detail: %s\n", st.Detail)
	}
	return nil
}

// cmdLogin logs into the gateway with username and password, and pushes the obtained credentials to the local daemon.
//
// Purpose: hosts without a GUI have no browser to push credentials, so this command provides a command-line alternative.
// The password is only obtained via interactive hidden input, not accepted as a command-line argument, to avoid leaking into shell history and process lists.
func cmdLogin(args []string) error {
	fs := flag.NewFlagSet("login", flag.ContinueOnError)
	gatewayFlag := fs.String("gateway", "", "gateway address (overrides config file)")
	userFlag := fs.String("u", "", "login username (interactive input if omitted)")
	configFlag := fs.String("config", "", "config file path (default ~/.haijunbot/daemon/config.yaml)")
	listenFlag := fs.String("listen", "", "local API listen address (overrides config file)")
	if err := fs.Parse(args); err != nil {
		return err
	}

	// Load config: used to fill in the gateway address and local listen address not given on the command line.
	cfgPath := *configFlag
	if cfgPath == "" {
		cfgPath = config.DefaultPath()
	}
	cfg, err := config.Load(cfgPath)
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}

	// Gateway address: command line takes priority, then the config file.
	gateway := login.NormalizeGateway(*gatewayFlag)
	if gateway == "" {
		gateway = login.NormalizeGateway(cfg.Gateway)
	}
	if gateway == "" {
		return fmt.Errorf("gateway address not specified; use -gateway, or configure gateway in the config file %s first", cfgPath)
	}

	// Local listen address: command line takes priority, then the config file, finally falling back to the default.
	listen := strings.TrimSpace(*listenFlag)
	if listen == "" {
		listen = strings.TrimSpace(cfg.Listen)
	}
	if listen == "" {
		listen = config.DefaultListen
	}

	// Username: command line takes priority, otherwise interactive input.
	username := strings.TrimSpace(*userFlag)
	if username == "" {
		fmt.Fprint(os.Stderr, "Username: ")
		reader := bufio.NewReader(os.Stdin)
		line, err := reader.ReadString('\n')
		if err != nil && strings.TrimSpace(line) == "" {
			return fmt.Errorf("failed to read username: %w", err)
		}
		username = strings.TrimSpace(line)
	}
	if username == "" {
		return fmt.Errorf("username cannot be empty")
	}

	// Password: interactive hidden input only.
	password, err := login.ReadPassword("Password: ")
	if err != nil {
		return fmt.Errorf("failed to read password: %w", err)
	}
	if password == "" {
		return fmt.Errorf("password cannot be empty")
	}

	fmt.Printf("[daemon] Logging into gateway %s ...\n", gateway)
	result, err := login.Login(gateway, username, password)
	if err != nil {
		return err
	}
	// Only print the masked token to avoid full credentials entering the logs.
	displayName := result.DisplayName
	if displayName == "" {
		displayName = result.Username
	}
	fmt.Printf("[daemon] Login successful: %s (token %s)\n", displayName, login.MaskToken(result.Token))

	// Push to the local daemon: pass name empty to keep the existing name for that gateway.
	if err := login.PushAuth(listen, gateway, result.Token, ""); err != nil {
		return err
	}
	fmt.Printf("[daemon] Pushed credentials to the local background service (%s); the daemon will connect to the gateway\n", listen)
	return nil
}

// cmdGatewayFilter reads and writes the gateway allow/deny list.
//
// Usage:
//
//	haijunbot-daemon gateway-filter get
//	haijunbot-daemon gateway-filter set -mode whitelist -pattern "*.example.com:*" -pattern "192.168.*:*"
//
// Implementation: sends an HTTP request to the local daemon's /api/gateway-filter (that endpoint is limited to
// local access), rather than modifying memory directly—this keeps a single source of truth with the running daemon,
// taking effect immediately and persisting to disk. The target is fixed to local loopback (127.0.0.1), explicitly bypassing the system proxy.
func cmdGatewayFilter(args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: haijunbot-daemon gateway-filter <get|set> [options]")
	}
	action := args[0]
	rest := args[1:]

	fs := flag.NewFlagSet("gateway-filter", flag.ContinueOnError)
	modeFlag := fs.String("mode", "", "list mode: off / whitelist / blacklist (required for set)")
	listenFlag := fs.String("listen", "", "local API listen address (overrides config file)")
	configFlag := fs.String("config", "", "config file path (default ~/.haijunbot/daemon/config.yaml)")
	var patterns patternFlags
	fs.Var(&patterns, "pattern", "match pattern (host:port, supports * and ?); can be specified multiple times")
	if err := fs.Parse(rest); err != nil {
		return err
	}

	// Local listen address: command line takes priority, then the config file, finally falling back to the default.
	cfgPath := *configFlag
	if cfgPath == "" {
		cfgPath = config.DefaultPath()
	}
	cfg, err := config.Load(cfgPath)
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}
	listen := strings.TrimSpace(*listenFlag)
	if listen == "" {
		listen = strings.TrimSpace(cfg.Listen)
	}
	if listen == "" {
		listen = config.DefaultListen
	}

	switch action {
	case "get":
		mode, pats, err := fetchGatewayFilter(listen)
		if err != nil {
			return err
		}
		printGatewayFilter(mode, pats)
		return nil
	case "set":
		mode := strings.TrimSpace(*modeFlag)
		if mode == "" {
			return fmt.Errorf("set requires -mode (off / whitelist / blacklist)")
		}
		if !gatewayfilter.ValidMode(mode) {
			return fmt.Errorf("mode must be one of off / whitelist / blacklist, current is %q", mode)
		}
		mode, pats, err := pushGatewayFilter(listen, mode, patterns)
		if err != nil {
			return err
		}
		fmt.Printf("[daemon] Gateway allow/deny list updated\n")
		printGatewayFilter(mode, pats)
		return nil
	default:
		return fmt.Errorf("unknown action: %s (should be get or set)", action)
	}
}

// patternFlags collects repeatable -pattern arguments.
type patternFlags []string

func (p *patternFlags) String() string { return strings.Join(*p, ",") }
func (p *patternFlags) Set(v string) error {
	*p = append(*p, v)
	return nil
}

// printGatewayFilter prints the list in a readable form.
func printGatewayFilter(mode string, patterns []string) {
	fmt.Printf("mode: %s\n", mode)
	if len(patterns) == 0 {
		fmt.Printf("patterns: (empty)\n")
		return
	}
	fmt.Printf("patterns:\n")
	for _, p := range patterns {
		fmt.Printf("  - %s\n", p)
	}
}

// gatewayFilterResponse is the response body of /api/gateway-filter.
type gatewayFilterResponse struct {
	Success  bool     `json:"success"`
	Mode     string   `json:"mode"`
	Patterns []string `json:"patterns"`
	Error    string   `json:"error"`
}

// gatewayFilterHTTPClient returns an HTTP client that bypasses the system proxy.
//
// The target is fixed to local loopback; going through the system proxy would fail to connect (the proxy does not forward loopback), so connect directly.
func gatewayFilterHTTPClient() *http.Client {
	return &http.Client{Timeout: 5 * time.Second, Transport: proxy.DirectTransport()}
}

// fetchGatewayFilter queries the local daemon for the current list.
func fetchGatewayFilter(listen string) (string, []string, error) {
	url := "http://" + listen + "/api/gateway-filter"
	resp, err := gatewayFilterHTTPClient().Get(url)
	if err != nil {
		return "", nil, fmt.Errorf("query failed: the local background service is not running (%s); start haijunbot-daemon first (%v)", listen, err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	var out gatewayFilterResponse
	if err := json.Unmarshal(raw, &out); err != nil {
		return "", nil, fmt.Errorf("failed to parse response: %w (raw response: %s)", err, strings.TrimSpace(string(raw)))
	}
	if !out.Success {
		return "", nil, fmt.Errorf("query failed: %s", out.Error)
	}
	return out.Mode, out.Patterns, nil
}

// pushGatewayFilter submits the new list to the local daemon.
func pushGatewayFilter(listen, mode string, patterns []string) (string, []string, error) {
	body, err := json.Marshal(map[string]any{"mode": mode, "patterns": patterns})
	if err != nil {
		return "", nil, fmt.Errorf("failed to serialize request: %w", err)
	}
	url := "http://" + listen + "/api/gateway-filter"
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return "", nil, fmt.Errorf("failed to build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := gatewayFilterHTTPClient().Do(req)
	if err != nil {
		return "", nil, fmt.Errorf("update failed: the local background service is not running (%s); start haijunbot-daemon first (%v)", listen, err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	var out gatewayFilterResponse
	if err := json.Unmarshal(raw, &out); err != nil {
		return "", nil, fmt.Errorf("failed to parse response: %w (raw response: %s)", err, strings.TrimSpace(string(raw)))
	}
	if !out.Success {
		return "", nil, fmt.Errorf("update failed (HTTP %d): %s", resp.StatusCode, out.Error)
	}
	return out.Mode, out.Patterns, nil

}

// newRuntimeRegistry creates the capability registry for the current platform and injects the external dependencies needed at runtime.
//
// Reuse point (see docs/js-plugin-design.md §7): shared by run, run-script, and script run,
// avoiding duplicate work. When store is nil (e.g. the run-script scenario without a credential store), provider injection is skipped,
// and capabilities such as browser.ext / ocr return a clear error rather than panicking when not injected.
func newRuntimeRegistry(store *auth.Store) *capability.Registry {
	registry := capability.NewRegistry()

	// Inject "get Token by gateway" into the capability layer so browser.ext.sync can download the extension package from the gateway itself.
	// The capability Handler signature cannot carry a credential store, so injection is used for decoupling (the capability package does not depend on auth).
	if store != nil {
		capability.SetBrowserExtCredentialProvider(func(gateway string) (string, bool) {
			creds, err := store.Get(gateway)
			if err != nil || creds.Token == "" {
				return "", false
			}
			return creds.Token, true
		})
		// Inject the "authenticated gateway list", used by ocr.recognize as a fallback when gateway is not explicitly specified.
		// Sorting ensures a stable order (the smallest address when there are multiple gateways), avoiding drift in results across calls.
		capability.SetOcrGatewayLister(func() []string {
			creds := store.List()
			out := make([]string, 0, len(creds))
			for _, c := range creds {
				if c.Gateway != "" && c.Token != "" {
					out = append(out, c.Gateway)
				}
			}
			sort.Strings(out)
			return out
		})
	}

	return registry
}

// storeFromEnv builds an auth.Store with credentials from environment variables, for standalone processes such as run-script
// to inject gateway credentials (making capabilities such as ocr.recognize / browser.ext available).
//
// Reads HAIJUNBOT_GATEWAY and HAIJUNBOT_AUTH_TOKEN; returns a non-nil store only when both are non-empty,
// otherwise returns nil (meaning no credentials; the capability layer returns a clear error rather than panicking).
func storeFromEnv() *auth.Store {
	gateway := os.Getenv("HAIJUNBOT_GATEWAY")
	token := os.Getenv("HAIJUNBOT_AUTH_TOKEN")
	if gateway == "" || token == "" {
		return nil
	}
	store := auth.NewStore()
	store.SetWithName(gateway, token, "run-script")
	return store
}

// cmdRunScript executes a JS script (the run-script subcommand).
//
// Usage: haijunbot-daemon run-script <file.js> [--arg key=value ...]
//   - <file.js>: the script file path (required)
//   - --arg key=value: optional, injects the script global object haijunbot.args (e.g. haijunbot.args.path)
//
// Within the script you can call haijunbot.cap / haijunbot.caps for automation; print/console.log output to stdout,
// console.error output to stderr; the script's top-level return value is printed to stdout.
func cmdRunScript(args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: haijunbot-daemon run-script <file.js> [--arg key=value ...]")
	}

	fs := flag.NewFlagSet("run-script", flag.ContinueOnError)
	argFlags := argFlags{}
	fs.Var(&argFlags, "arg", "script argument key=value (can be specified multiple times)")
	// Manual parsing: the first non-flag argument is the script file path, the rest are --arg.
	// fs.Parse would error on unknown positional arguments, so separate the script path first, then parse the options.
	scriptPath := ""
	rest := make([]string, 0, len(args))
	for _, a := range args {
		if scriptPath == "" && !isFlag(a) {
			scriptPath = a
			continue
		}
		rest = append(rest, a)
	}
	if scriptPath == "" {
		return fmt.Errorf("usage: haijunbot-daemon run-script <file.js> [--arg key=value ...]")
	}
	if err := fs.Parse(rest); err != nil {
		return err
	}

	// Read the script file.
	source, err := os.ReadFile(scriptPath)
	if err != nil {
		return fmt.Errorf("failed to read script %s: %w", scriptPath, err)
	}

	// Assemble the capability registry (reusing the assembly logic of the run flow).
	// run-script is a standalone process with no credential store by default (store=nil);
	// capabilities that depend on gateway credentials return a clear error. If the caller sets HAIJUNBOT_GATEWAY +
	// HAIJUNBOT_AUTH_TOKEN environment variables, credentials are injected from them, making those capabilities available within the script.
	registry := newRuntimeRegistry(storeFromEnv())

	// Create the runtime and inject the haijunbot capability object.
	r := jsruntime.New()
	r.SetOutput(func(s string) { fmt.Print(s) }, func(s string) { fmt.Fprint(os.Stderr, s) })
	if err := jsruntime.InstallBridge(r, registry); err != nil {
		return fmt.Errorf("failed to inject haijunbot capability object: %w", err)
	}

	// Inject script arguments haijunbot.args.
	if err := jsruntime.InstallScriptArgs(r, argFlags); err != nil {
		return fmt.Errorf("failed to inject haijunbot.args: %w", err)
	}

	// Execute the script.
	result, err := r.RunScriptFile(scriptPath, string(source))
	if err != nil {
		// Script execution errors are output to stderr (including the stack), and an error is returned so the exit code is non-zero.
		fmt.Fprintf(os.Stderr, "[run-script] execution failed: %v\n", err)
		return fmt.Errorf("script execution failed: %v", err)
	}

	// Print the script's top-level return value to stdout when it is not undefined.
	if result != nil {
		if s, ok := result.(string); ok {
			fmt.Println(s)
		} else {
			fmt.Println(result)
		}
	}
	return nil
}

// argFlags collects --arg key=value arguments.
type argFlags map[string]string

func (a argFlags) String() string { return "" }
func (a argFlags) Set(v string) error {
	if a == nil {
		return nil
	}
	key, val, ok := strings.Cut(v, "=")
	if !ok || key == "" {
		return fmt.Errorf("--arg requires the key=value format, got: %q", v)
	}
	a[key] = val
	return nil
}

// printUsage prints the usage description.
func printUsage() {
	fmt.Print(`haijunbot-daemon - HaijunBot local daemon

Usage:
  haijunbot-daemon [run] [options]     run the daemon in the foreground (default behavior)
  haijunbot-daemon install [options]   install as a system service and enable auto-start on boot
  haijunbot-daemon uninstall           stop and uninstall the system service
  haijunbot-daemon start               start the service
  haijunbot-daemon stop                stop the service
  haijunbot-daemon restart             restart the service
  haijunbot-daemon status              view service status
  haijunbot-daemon login [options]     log into the gateway with username and password and push credentials to the local service
  haijunbot-daemon gateway-filter <get|set> [options]  read/write the gateway allow/deny list (local only)
  haijunbot-daemon run-script <file.js> [--arg key=value ...]  execute a JS script (can call haijunbot capabilities)
  haijunbot-daemon self-update-apply [options]  auto-update helper (internal use, do not call manually)

Options (shared by run / install):
  -listen string     local API listen address (overrides config file)
  -gateway string    default gateway address (overrides config file)
  -config string     config file path (default ~/.haijunbot/daemon/config.yaml)
  -web-listen string  Web login service listen address (overrides config file, default 0.0.0.0:17801; pass an empty string to disable)

Options (login only):
  -gateway string    gateway address (overrides config file)
  -u string          login username (interactive input if omitted; the password is always entered interactively)
  -listen string     local API listen address (overrides config file)
  -config string     config file path (default ~/.haijunbot/daemon/config.yaml)
`)
}

// isNonLoopbackListen reports whether the listen address is exposed externally (non-loopback).
// Only used to decide whether to print a security risk notice: binding to 127.0.0.1 / ::1 should not produce a false positive.
// Rules:
//   - an empty string means the service is disabled, returns false;
//   - an empty host part (e.g. ":17801") or 0.0.0.0 / :: means listening on all interfaces, returns true;
//   - a loopback host (127.0.0.0/8, ::1, localhost) returns false;
//   - everything else (including a specific intranet IP or hostname) is treated as externally exposed, returns true.
func isNonLoopbackListen(addr string) bool {
	addr = strings.TrimSpace(addr)
	if addr == "" {
		return false
	}
	host, _, err := net.SplitHostPort(addr)
	if err != nil {
		// On parse failure, be conservative: since loopback cannot be confirmed, treat it as externally exposed.
		return true
	}
	host = strings.TrimSpace(host)
	if host == "" {
		return true
	}
	if strings.EqualFold(host, "localhost") {
		return false
	}
	if ip := net.ParseIP(host); ip != nil {
		return !ip.IsLoopback()
	}
	// A hostname cannot be determined, so treat it as externally exposed.
	return true
}

func runDaemon(args []string) {
	// Hide our own console window: on Windows, when a scheduled task starts a console program interactively,
	// the system allocates a visible console window, leaving a persistent black box on the user's desktop.
	// No-op on non-Windows platforms.
	service.HideSelfConsole()

	// Persist logs to disk: on Windows, when started by a scheduled task, stderr has no receiver and all logs would be lost.
	// Here a copy is also written to ~/.haijunbot/logs/daemon.log for later troubleshooting; failure just falls back to stderr.
	if logPath := daemonlog.Setup(); logPath != "" {
		log.Printf("[daemon] Log file: %s", logPath)
	}

	fs := flag.NewFlagSet("run", flag.ExitOnError)
	listenFlag := fs.String("listen", "", "local API listen address (overrides config file)")
	gatewayFlag := fs.String("gateway", "", "default gateway address (overrides config file)")
	configFlag := fs.String("config", "", "config file path (default ~/.haijunbot/daemon/config.yaml)")
	webListenFlag := fs.String("web-listen", "", "Web login service listen address (overrides config file; pass an empty string to disable)")
	_ = fs.Parse(args)

	cfgPath := *configFlag
	if cfgPath == "" {
		cfgPath = config.DefaultPath()
	}
	cfg, err := config.Load(cfgPath)
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}
	if *listenFlag != "" {
		cfg.Listen = *listenFlag
	}
	if *gatewayFlag != "" {
		cfg.Gateway = *gatewayFlag
	}
	// -web-listen needs to distinguish "not provided" (use the config file) from "explicitly passed an empty string" (disable the service):
	// the flag default is also an empty string, so the value cannot be used to tell them apart; use fs.Visit to detect whether the option actually appeared.
	webListenSet := false
	fs.Visit(func(f *flag.Flag) {
		if f.Name == "web-listen" {
			webListenSet = true
		}
	})
	if webListenSet {
		cfg.WebListen = *webListenFlag
	}
	if err := cfg.Validate(); err != nil {
		log.Fatalf("invalid config: %v", err)
	}

	// The credential persistence file is in the same directory as config.yaml; loaded at startup to auto-restore the login state after a restart.
	// If the file is missing or corrupted, LoadStore silently returns an empty Store, not affecting normal startup.
	credentialsPath := ""
	if cfgPath != "" {
		credentialsPath = filepath.Join(filepath.Dir(cfgPath), "credentials.json")
	}
	store := auth.LoadStore(credentialsPath)

	// Exposed to the auto-update flow, used to temporarily persist credentials before updating (see saveCurrentCredentialsForUpdate).
	currentStore = store

	// If the last run was "auto-update -> restart", restore the temporarily saved credentials at startup and immediately delete the file.
	// Must be done before the Manager is constructed: after restoring, a connection is actively initiated below.
	restoredCreds, restored := selfupdate.LoadAndClearTokenState()
	if restored {
		store.SetWithName(restoredCreds.Gateway, restoredCreds.Token, restoredCreds.Name)
		log.Printf("[daemon] Restored credentials from the auto-update handoff file (gateway %s); the file has been deleted", restoredCreds.Gateway)
	}

	// Clean up intermediate artifacts left by the last auto-update (attempt state, .new/.helper.exe remnants).
	// Placed here because: on Windows the update goes through the helper path, the parent process starts the helper and exits immediately,
	// and the helper cannot delete itself while running; only "when the new process starts after the replacement completes" can it safely clean up.
	// Called unconditionally (independent of restored): the function is idempotent, and only clears the attempt state when "target version == current version";
	// failure backoff/circuit-breaker information is unaffected.
	selfupdate.CleanupAfterUpdate(version)

	// Register the current platform's capabilities for execution when the gateway dispatches commands.
	registry := newRuntimeRegistry(store)
	log.Printf("[daemon] Registered %d platform capabilities", len(registry.ListForPlatform(capability.Current())))

	// Gateway allow/deny list: configured by the daemon itself (config.yaml), modifiable locally only via
	// /api/gateway-filter or `haijunbot-daemon gateway-filter`.
	// Deliberately does not go through front-end page pushes: the front end and the daemon may be on different machines, so the push semantics do not apply.
	// The list only blocks "new connections"; existing connections are not actively disconnected (see ConnectWithName).
	gwFilter := gatewayfilter.New(cfg.GatewayFilterMode, cfg.GatewayFilterPatterns)
	if mode, patterns := gwFilter.Snapshot(); mode != gatewayfilter.ModeOff {
		log.Printf("[daemon] Gateway allow/deny list enabled: mode=%s patterns=%v", mode, patterns)
	}

	manager := wsclient.NewManagerWithOptions(wsclient.ManagerOptions{
		Options: wsclient.Options{
			// Gateway/Token are overridden by Connect per specific gateway; not preset here.
			ClientID:          buildClientID(),
			Version:           version,
			Registry:          registry,
			HeartbeatInterval: cfg.HeartbeatInterval,
			ReconnectMin:      cfg.ReconnectMin,
			ReconnectMax:      cfg.ReconnectMax,
		},
		// Allow/deny list interception: disallowed gateways do not establish connections.
		AllowGateway: gwFilter.Allows,
		OnGatewayStateChange: func(gateway, state string) {
			log.Printf("[daemon] Connection state: %s (%s)", state, gateway)
		},
		OnGatewayAuthError: func(gateway string, code int, reason string) {
			// Authentication failure only affects that gateway: mark its Token as invalid and wait for the web page to push again.
			log.Printf("[daemon] Gateway %s authentication failed (close code %d); marking Token invalid, waiting for the web page to push again", gateway, code)
			store.MarkTokenInvalid(gateway)
		},
		OnGatewayHelloAck: func(gateway, sessionID, latestExtVersion string) {
			// The latest extension version sent by the gateway during the handshake (legacy field, kept for compatibility).
			// The version number is globally unified; actual sync is based on daemon_update.latest_version
			// (see OnGatewayDaemonUpdate); this is only recorded, used as a fallback when the switch triggers a recheck.
			rememberGatewayExtVersion(gateway, latestExtVersion)
		},
		OnGatewayDaemonUpdate: func(gateway, sessionID string, info map[string]any) {
			// The gateway informs the daemon of a new version during the handshake; constrained by the "auto-update" switch, executed asynchronously.
			// Placed in a separate goroutine: downloading + replacing may take time and must not block the WS read loop.
			maybeAutoUpdateDaemon(gateway, sessionID, info)
			// The version number is globally unified (the extension and daemon share the same version), so daemon_update.latest_version
			// is also "the latest extension version packaged by the gateway": this drives automatic extension sync.
			// Recorded for use when "the extension switch is later turned on" for a recheck (the switch is often pushed later than the handshake).
			if latest, _ := info["latest_version"].(string); latest != "" {
				rememberGatewayExtVersion(gateway, latest)
				maybeAutoSyncBrowserExt(gateway, latest)
			}
		},
	})

	// Exposed to the auto-update flow, used to report update progress (see reportDaemonUpdateStatus).
	currentManager = manager

	// If the last run was "auto-update -> restart" and credentials were restored, actively initiate a connection (otherwise wait for the web page to push).
	if restored {
		manager.ConnectWithName(restoredCreds.Gateway, restoredCreds.Token, restoredCreds.Name)
	}

	// Credentials restored from the persistence file: actively connect to all authenticated gateways, auto-restoring the login state after a restart.
	// ConnectWithName is idempotent: it will not establish a duplicate connection when it points to the same gateway as the self-update handoff restore above,
	// and that gateway's token has already been overwritten by SetWithName to the handoff value, so the correct token is used when iterating.
	for _, c := range store.List() {
		if c.Gateway != "" && c.Token != "" {
			manager.ConnectWithName(c.Gateway, c.Token, c.Name)
		}
	}

	api := localapi.New(store, manager, version)
	// When the switch changes from off to on, perform an extra extension sync check: the daemon only checks once at hello_ack,
	// while the front end usually pushes the switch later than hello_ack; without a recheck it would always consider it "disabled".
	api.SetOnBrowserExtEnabled(func() { onBrowserExtSwitchEnabled(manager) })
	// Periodic fallback: check extension version sync for connected gateways every 10 minutes (see function comment).
	startBrowserExtPeriodicSync(manager)
	// Gateway allow/deny list: reads the current in-memory state; on update, changes the in-memory state and persists to config.yaml.
	// The endpoint itself enforces loopback source validation within localapi (local access only).
	api.SetGatewayFilter(
		func() (string, []string) { return gwFilter.Snapshot() },
		func(mode string, patterns []string) (string, []string, error) {
			gwFilter.Set(mode, patterns)
			actualMode, actualPatterns := gwFilter.Snapshot()
			if err := config.UpdateGatewayFilter(cfgPath, actualMode, actualPatterns); err != nil {
				// The in-memory state was updated but persistence failed: return an error so the caller knows (it will be lost after a restart).
				return actualMode, actualPatterns, err
			}
			return actualMode, actualPatterns, nil
		},
	)

	srv := localapi.NewHTTPServer(cfg.Listen, api.Handler())

	// Web login service: for browsers on **other machines** to access (hosts without a GUI have no browser).
	// Independent from the local API; an empty WebListen means the service is disabled.
	var webSrv *http.Server
	if strings.TrimSpace(cfg.WebListen) != "" {
		ui := webui.New(store, manager, version)
		webSrv = localapi.NewHTTPServer(cfg.WebListen, ui.Handler())
	}

	// If the config already has a gateway but no Token, do not connect actively (wait for the web page to push).
	log.Printf("[daemon] haijunbot-daemon %s started, local API: http://%s", version, cfg.Listen)
	if webSrv != nil {
		// Only warn about risk when a non-loopback address is actually bound, avoiding a false positive when binding 127.0.0.1.
		if isNonLoopbackListen(cfg.WebListen) {
			log.Printf("[daemon] Web login page: http://%s/ (bound to a non-loopback address; use only on a trusted intranet)", cfg.WebListen)
		} else {
			log.Printf("[daemon] Web login page: http://%s/", cfg.WebListen)
		}
	}
	if cfgPath != "" {
		log.Printf("[daemon] Config file: %s", cfgPath)
	}

	errCh := make(chan error, 1)
	go func() {
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()
	if webSrv != nil {
		go func() {
			if err := webSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
				// A failure to start the Web login service should not bring down the whole daemon (the local API is still available),
				// so only log it, helping users on GUI-less hosts troubleshoot issues such as port conflicts.
				log.Printf("[daemon] Failed to start the Web login service (%s): %v", cfg.WebListen, err)
			}
		}()
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	select {
	case err := <-errCh:
		log.Fatalf("failed to start local API: %v", err)
	case <-ctx.Done():
		log.Printf("[daemon] Received exit signal, shutting down...")
	}

	manager.DisconnectAll()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*1e9)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("[daemon] Failed to shut down local API: %v", err)
	}
	if webSrv != nil {
		if err := webSrv.Shutdown(shutdownCtx); err != nil {
			log.Printf("[daemon] Failed to shut down Web login service: %v", err)
		}
	}
}

// buildClientID generates the client identifier: daemon-<hostname>-<pid>.
func buildClientID() string {
	host, err := os.Hostname()
	if err != nil || host == "" {
		host = "unknown"
	}
	return fmt.Sprintf("daemon-%s-%d", host, os.Getpid())
}

// browserExtSyncMu serializes extension sync, avoiding concurrent writes to the same directory when multiple gateways handshake at the same time.
var browserExtSyncMu sync.Mutex

// browserExtSyncInterval is the interval for the periodic browser extension sync check.
//
// As a safety fallback beyond the handshake/switch events: when the gateway has not reconnected for a long time and the switch has long been on,
// if the gateway side publishes a new extension version, local event triggers alone will not notice it, so this timer periodically covers it.
const browserExtSyncInterval = 10 * time.Minute

// gatewayExtVersionMu protects gatewayExtVersions.
var gatewayExtVersionMu sync.Mutex

// gatewayExtVersions records the latest extension version most recently sent by each gateway (keyed by GatewayKey).
//
// Why needed: maybeAutoSyncBrowserExt's version number comes from the handshake (daemon_update), and
// the "switch turned on" event happens after the handshake, when there is no new handshake to rely on, so we can only look back here
// at the cached value; otherwise the recheck cannot obtain the version number and cannot determine whether syncing is needed.
var gatewayExtVersions = map[string]string{}

// rememberGatewayExtVersion records the latest extension version most recently sent by a gateway.
//
// An empty string means the gateway did not provide a version: ignore it rather than overwrite, to avoid an old hello_ack empty value
// clobbering the real version number later brought by daemon_update (the two arrive one after another in the same handshake round).
func rememberGatewayExtVersion(gateway, latestVersion string) {
	if latestVersion == "" {
		return
	}
	key := auth.GatewayKey(gateway)
	gatewayExtVersionMu.Lock()
	defer gatewayExtVersionMu.Unlock()
	gatewayExtVersions[key] = latestVersion
}

// gatewayExtVersionOf returns the latest extension version most recently sent by a gateway; returns ("", false) when there is no record.
func gatewayExtVersionOf(gateway string) (string, bool) {
	key := auth.GatewayKey(gateway)
	gatewayExtVersionMu.Lock()
	defer gatewayExtVersionMu.Unlock()
	v, ok := gatewayExtVersions[key]
	return v, ok
}

// onBrowserExtSwitchEnabled is called when the "auto-install/update browser extension" switch changes from off to on,
// to perform an extra sync check for all connected gateways whose gateway extension version is known.
//
// Why needed: after the daemon starts it first connects to the gateway, and when hello_ack is received the switch is still at the default false (the front end has not yet
// pushed it), so it prints "disabled, skipping auto sync"; the front end pushes the switch afterwards, but the daemon does not
// recheck, so the user has clearly enabled the switch yet it never syncs until the next reconnect. Here, when the switch is turned on,
// actively perform one recheck to eliminate this timing dependency.
func onBrowserExtSwitchEnabled(manager *wsclient.Manager) {
	for _, st := range manager.Status() {
		if !st.Connected {
			continue
		}
		latest, ok := gatewayExtVersionOf(st.Gateway)
		if !ok {
			// This gateway has not yet sent a version (no hello_ack received); handle it during its own handshake.
			continue
		}
		log.Printf("[daemon] Extension switch is on; performing an extra sync check (gateway %s, gateway version %q)", st.Gateway, latest)
		maybeAutoSyncBrowserExt(st.Gateway, latest)
	}
}

// startBrowserExtPeriodicSync performs a browser extension version sync check for connected
// gateways every browserExtSyncInterval (10 minutes).
//
// Why needed: the existing trigger points for extension sync (gateway handshake hello_ack, switch "off->on" transition)
// all depend on events. If the gateway has not reconnected for a long time and the switch has long been on, while the gateway side publishes a new extension version,
// local event triggers alone cannot notice it, and it only syncs on the next reconnect. This timer acts as a fallback, periodically comparing "the gateway's latest
// version" with the local one.
//
// Safety: this only periodically triggers the check; whether syncing actually happens is still gated by the internal
// switch check + version comparison + browserExtSyncMu mutex inside maybeAutoSyncBrowserExt, bypassing no existing constraints; any failure
// only logs and never affects connections or existing capabilities.
func startBrowserExtPeriodicSync(manager *wsclient.Manager) {
	go func() {
		ticker := time.NewTicker(browserExtSyncInterval)
		defer ticker.Stop()
		for range ticker.C {
			for _, st := range manager.Status() {
				if !st.Connected {
					continue
				}
				latest, ok := gatewayExtVersionOf(st.Gateway)
				if !ok {
					// This gateway has not yet sent a version (no hello_ack received); handle it during its own handshake.
					continue
				}
				maybeAutoSyncBrowserExt(st.Gateway, latest)
			}
		}
	}()
}

// maybeAutoSyncBrowserExt asynchronously syncs the extension package when the gateway sends the latest extension version and it differs from the local one.
//
// Design points:
//   - Constrained by the "auto-install/update browser extension" switch: skipped outright when the switch is off (default),
//     with no download and no goroutine started. The switch, once explicitly turned on by the user in the Web settings UI, is pushed to the
//     local daemon along with the login state (in-memory only, not persisted), so after the daemon restarts it returns to off, waiting
//     for the front end to push again—no auto sync without a push, which is the safe default;
//   - Returns immediately, putting download/decompress into a separate goroutine (downloading may take seconds), not blocking the WS read loop;
//   - Skipped outright when versions match, avoiding repeated downloads on every reconnect;
//   - Any failure only logs and never affects connections or existing capabilities;
//   - Does not restart the browser: it only persists the new version to disk, and the user manually refreshes at chrome://extensions.
//
// Note: this switch only constrains the "auto sync" here; the manual capability browser.ext.sync is explicitly
// invoked by the user and is not constrained by this switch.
func maybeAutoSyncBrowserExt(gateway, latestVersion string) {
	// The switch check must be at the function entry, outside the goroutine: return early when off, avoiding starting a useless goroutine.
	if !capability.AutoInstallBrowserExt() {
		log.Printf("[daemon] Auto-install/update browser extension is off; skipping auto sync (gateway %s, gateway version %q)",
			gateway, latestVersion)
		return
	}
	latestVersion = strings.TrimSpace(latestVersion)
	if latestVersion == "" {
		// The gateway did not provide a version (old gateway or read failure); cannot determine whether an update is needed.
		return
	}
	localVersion := capability.LocalBrowserExtVersion()
	if localVersion == latestVersion {
		return
	}

	go func() {
		// Only one sync task is allowed at a time, avoiding concurrent directory replacements interfering with each other.
		browserExtSyncMu.Lock()
		defer browserExtSyncMu.Unlock()

		// Check again after acquiring the lock: it may have already been synced to the target version by another gateway while waiting.
		if capability.LocalBrowserExtVersion() == latestVersion {
			return
		}
		log.Printf("[daemon] Extension version mismatch detected (local %q -> gateway %q); starting auto sync (gateway %s)",
			localVersion, latestVersion, gateway)

		count, version, err := capability.SyncBrowserExt(gateway, browserExtTokenFor(gateway))
		if err != nil {
			log.Printf("[daemon] Failed to auto-sync browser extension (gateway %s): %v", gateway, err)
			return
		}
		log.Printf("[daemon] Browser extension synced to %q (%d files, directory %s); "+
			"click \"Refresh\" at chrome://extensions in the browser to make the new version take effect",
			version, count, capability.BrowserExtDirOrEmpty())

		// After syncing completes, automatically open the local browser's extensions page: the user needs to click "Refresh" once on the extensions page
		// (if installed) or "Load unpacked" (if not installed) for the new version to take effect; opening it automatically
		// saves manually focusing the window -> Ctrl+L -> typing the URL -> Enter.
		// Failure only logs: the extension files were successfully persisted, and failing to open the page does not affect the sync result.
		opened, openErr := capability.OpenBrowserExtensionsPage()
		if openErr != nil {
			log.Printf("[daemon] Failed to auto-open the browser extensions page (gateway %s): %v", gateway, openErr)
		} else if len(opened) > 0 {
			log.Printf("[daemon] Auto-opened the browser extensions page: %s", strings.Join(opened, ", "))
		} else {
			log.Printf("[daemon] No browser available to open (neither Edge nor Chrome is installed); please open the extensions page manually")
		}
	}()
}

// browserExtTokenFor gets the Token for the specified gateway; returns an empty string when there are no credentials (sync will then error and log it).
func browserExtTokenFor(gateway string) string {
	token, ok := capability.BrowserExtToken(gateway)
	if !ok {
		return ""
	}
	return token
}

// daemonUpdateMu serializes auto-updates, avoiding concurrent download/replace interfering with each other when multiple gateways handshake at the same time.
var daemonUpdateMu sync.Mutex

// daemonRetryScheduled marks that "there is already a pending backoff retry timer".
//
// Why needed: after the backoff expires an active retry is required (see the maybeAutoUpdateDaemon comment below), while the trigger
// point (WS handshake) may arrive multiple times in a short period (e.g. the front end repeatedly pushing credentials causing reconnects). Without dedup, each
// trigger would start another timer, and when the window elapses multiple goroutines compete for daemonUpdateMu at once, forming a retry
// storm. On timer expiry, clear this flag first then execute, ensuring future re-scheduling is still possible.
var daemonRetryScheduled bool

// daemonRetryMu protects daemonRetryScheduled.
var daemonRetryMu sync.Mutex

// scheduleDaemonUpdateRetry automatically retries the auto-update once after the given duration.
//
// Why an active retry is required: maybeAutoUpdateDaemon's trigger is receiving hello_ack on the WS handshake, but
// when the connection is stable there are only ping/pong heartbeats and no hello_ack; and when the front end repeatedly pushes the same credentials,
// ConnectWithName skips rebuilding the connection due to the idempotency check (see wsclient/manager.go), likewise producing no
// hello_ack. Without actively scheduling a timer, no event would wake the check after the backoff window expires, and the update would
// stall forever in "backoff".
//
// Dedup: only one pending timer is allowed at a time; if already scheduled, ignore this request.
func scheduleDaemonUpdateRetry(gateway, sessionID string, info map[string]any, after time.Duration) {
	daemonRetryMu.Lock()
	if daemonRetryScheduled {
		daemonRetryMu.Unlock()
		return
	}
	daemonRetryScheduled = true
	daemonRetryMu.Unlock()

	log.Printf("[daemon] Will retry auto-update after %s (gateway %s)", after.Round(time.Second), gateway)
	time.AfterFunc(after, func() {
		// Clear the flag before calling: even if the retry fails again, the next round of timers can be scheduled again.
		daemonRetryMu.Lock()
		daemonRetryScheduled = false
		daemonRetryMu.Unlock()

		log.Printf("[daemon] Backoff expired; retrying daemon update automatically (gateway %s)", gateway)
		maybeAutoUpdateDaemon(gateway, sessionID, info)
	})
}

// maybeAutoUpdateDaemon asynchronously performs the update when the gateway dispatches a daemon update command.
//
// Design points:
//   - Unconditional auto-update: the daemon must stay on the same version as the gateway; the gateway sends its own
//     version as the "latest version" in hello_ack, and the daemon compares and auto-updates, with no switch and no environment variable;
//   - Returns immediately, putting download/replace into a separate goroutine (may take seconds), not blocking the WS read loop;
//   - Temporarily persists the current credentials before updating, to restore the login state after a restart (see selfupdate.SaveTokenState);
//   - Any failure only logs and never affects connections or existing capabilities;
//   - Actively schedules a timed retry after the backoff expires (see scheduleDaemonUpdateRetry), not relying on external handshake events.
func maybeAutoUpdateDaemon(gateway, sessionID string, info map[string]any) {
	parsed, err := selfupdate.ParseUpdateInfo(info)
	if err != nil {
		// Silently skip when no update is available; other parse errors only log.
		if !errors.Is(err, selfupdate.ErrNotAvailable) {
			log.Printf("[daemon] Failed to parse daemon update command (gateway %s): %v", gateway, err)
		}
		return
	}

	go func() {
		// Only one update task is allowed at a time, avoiding concurrent replacement of the same executable.
		daemonUpdateMu.Lock()
		defer daemonUpdateMu.Unlock()

		// Anti-duplication: circuit breaking (restart loop) + no retry on same-version failure + failure backoff.
		// The trigger is every WS handshake; without constraints, a failed update would retry infinitely with each reconnect.
		state, _ := selfupdate.LoadAttemptState()
		if skip, reason := selfupdate.ShouldSkipUpdate(state, version, parsed.LatestVersion, selfupdate.NowUnix()); skip {
			log.Printf("[daemon] Skipping auto-update (gateway %s): %s", gateway, reason)
			// If in backoff, schedule an active retry on expiry; RetryAfter returning 0 means the circuit is broken (waiting for the gateway to send a new version),
			// in which case no retry must be scheduled, or it would fall into a restart loop.
			if wait := selfupdate.RetryAfter(state, version, parsed.LatestVersion, selfupdate.NowUnix()); wait > 0 {
				scheduleDaemonUpdateRetry(gateway, sessionID, info, wait+time.Second)
			}
			return
		}

		target, err := service.InstalledBinaryPath()
		if err != nil {
			log.Printf("[daemon] Cannot determine the executable path; skipping auto-update: %v", err)
			return
		}

		// The update restarts the service, so first temporarily persist the current credentials to restore the login state after a restart.
		// A persistence failure does not block the update (the worst case is just needing to re-push credentials after a restart).
		saveCurrentCredentialsForUpdate(gateway)

		// Record "an attempt to update to this version has started" and set InProgress: if the new version fails to start after replacement,
		// the new process reads this mark at startup and, with the version unchanged, breaks the circuit, avoiding infinite restarts.
		// Reset the count when the target version changes (treated as a new opportunity).
		attempts := state.Attempts
		if !selfupdate.SameVersion(state.TargetVersion, parsed.LatestVersion) {
			attempts = 0
		}
		_ = selfupdate.SaveAttemptState(selfupdate.AttemptState{
			TargetVersion:   parsed.LatestVersion,
			Attempts:        attempts,
			LastAttemptUnix: selfupdate.NowUnix(),
			InProgress:      true,
		})

		log.Printf("[daemon] New daemon version %s detected (current %s); starting auto-update (gateway %s, target %s)",
			parsed.LatestVersion, parsed.CurrentVersion, gateway, target)

		err = selfupdate.Run(selfupdate.Options{
			Info:       parsed,
			Version:    version,
			TargetPath: target,
			Restart:    true,
			// Report update progress to the gateway (one-way daemon.update.status; the gateway only logs it).
			// The connection may already be down (before restart); a Send failure only logs and does not affect the update flow.
			Report: func(state selfupdate.UpdateState, errMsg string) {
				reportDaemonUpdateStatus(gateway, parsed.LatestVersion, state, errMsg)
			},
		})
		if err != nil {
			// Failure: increment the attempt count and record the reason for backoff decisions at the next handshake.
			_ = selfupdate.SaveAttemptState(selfupdate.AttemptState{
				TargetVersion:   parsed.LatestVersion,
				Attempts:        attempts + 1,
				LastAttemptUnix: selfupdate.NowUnix(),
				LastError:       err.Error(),
				InProgress:      false,
			})
			log.Printf("[daemon] Auto-update of daemon failed (gateway %s, attempt %d): %v", gateway, attempts+1, err)
			return
		}
		// Success: clear the attempt state (the replacement is complete on Linux; on Windows it has been handed to the helper).
		// If the subsequent restart fails, the new process reads the cleared state and will not falsely break the circuit.
		_ = selfupdate.ClearAttemptState()
		log.Printf("[daemon] daemon auto-update completed (version %s)", parsed.LatestVersion)
	}()
}

// saveCurrentCredentialsForUpdate temporarily persists the current credentials of the specified gateway, for restoring after an update restart.
//
// When there are no credentials or persistence fails, only log without returning an error (the caller should not interrupt the update flow because of this).
func saveCurrentCredentialsForUpdate(gateway string) {
	creds, err := currentStore.Get(gateway)
	if err != nil || creds.Token == "" {
		log.Printf("[daemon] No credentials found for gateway %s before update; will need to push again after restart", gateway)
		return
	}
	state := selfupdate.TokenState{
		Gateway:     creds.Gateway,
		Token:       creds.Token,
		Name:        creds.Name,
		SavedAtUnix: selfupdate.NowUnix(),
	}
	if err := selfupdate.SaveTokenState(state); err != nil {
		log.Printf("[daemon] Failed to save credentials before update (will need to push again after restart): %v", err)
		return
	}
	log.Printf("[daemon] Temporarily saved credentials for gateway %s before update; will auto-restore after restart", gateway)
}

// reportDaemonUpdateStatus reports update progress to the gateway as a one-way daemon.update.status.
//
// The gateway only logs and does not reply (see daemon/docs/daemon-self-update-protocol.md for the protocol).
// The connection may be down (especially during the restarting phase) or the gateway may no longer be in the manager; in that case only log,
// and never interrupt the update flow because of a reporting failure.
func reportDaemonUpdateStatus(gateway, version string, state selfupdate.UpdateState, errMsg string) {
	client, ok := currentManager.Get(gateway)
	if !ok {
		log.Printf("[daemon] Cannot report update state %s (gateway %s not connected)", state, gateway)
		return
	}
	payload := map[string]any{
		"type":    "daemon.update.status",
		"state":   string(state),
		"version": version,
	}
	if errMsg != "" {
		payload["error"] = errMsg
	}
	if err := client.Send(payload); err != nil {
		log.Printf("[daemon] Failed to report update state %s (gateway %s): %v", state, gateway, err)
		return
	}
	log.Printf("[daemon] Update state reported: state=%s version=%s (gateway %s)", state, version, gateway)
}
