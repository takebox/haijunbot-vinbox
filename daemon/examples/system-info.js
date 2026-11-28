// system-info.js — example that reads system information
//
// Usage: haijunbot-daemon run-script examples/system-info.js
//
// Demonstrates:
//   - haijunbot.cap() generic invocation capability
//   - print() / console.log() output to stdout
//   - the script's top-level return value printed to stdout

// Method 1: haijunbot.cap(name, params) generic entry point (returns {success, data, error})
const res = haijunbot.cap("linux.system.info", {});
if (res.success) {
  print("Hostname:", res.data.hostname);
  print("OS:", res.data.os_name, res.data.os_version, res.data.arch);
  print("Kernel:", res.data.kernel);
  print(
    "Memory:",
    Math.round(res.data.mem_available_kb / 1024) +
      " MB available / " +
      Math.round(res.data.mem_total_kb / 1024) +
      " MB total",
  );
} else {
  console.error("failed to get system info:", res.error);
}

// Method 2: haijunbot.caps.<domain>.<action>(params) nested namespace (throws on failure)
try {
  const info = haijunbot.caps.linux.system.info({});
  print("CPU cores:", info.cpu_count);
} catch (e) {
  console.error("nested call failed:", e.message);
}

// The top-level return value is printed to stdout by run-script
("system info read complete");
