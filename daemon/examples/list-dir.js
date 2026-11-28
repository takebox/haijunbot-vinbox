// list-dir.js — example that lists directory contents
//
// Usage: haijunbot-daemon run-script examples/list-dir.js --arg path=/tmp
//
// Demonstrates:
//   - haijunbot.args script parameter injection (--arg key=value)
//   - haijunbot.cap() calling linux.fs.list
//   - iterating over the returned entries array

// Read the directory path from haijunbot.args (defaults to the current directory)
const path = haijunbot.args.path || ".";

const res = haijunbot.cap("linux.fs.list", { path: path });
if (!res.success) {
  console.error("failed to list directory:", res.error);
  throw new Error("directory listing failed: " + path);
}

print("Directory:", res.data.path, "(total " + res.data.count + " entries)");
print("----------------------------------------");

// Iterate over entries, prefix directories with [D]
for (const entry of res.data.entries) {
  const prefix = entry.is_dir ? "[D] " : "    ";
  print(prefix + entry.name);
}

// Top-level return value
("directory listing complete");
