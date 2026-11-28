// outlook_ui.js — reads new Outlook mails via UI operations (screenshot + OCR) (background service script)
//
// Applicable to: machines such as SF-PC that use "new Outlook (olk.exe)"; the classic MAPI COM
// cannot read mails there, so content can only be obtained via the UI (screenshot + OCR).
//
// Usage (on Windows; the daemon must support run-script):
//   haijunbot-daemon run-script examples/outlook_ui.js --arg action=list
//   haijunbot-daemon run-script examples/outlook_ui.js --arg action=read --arg subject=Anna
//   haijunbot-daemon run-script examples/outlook_ui.js --arg action=read --arg index=0
//
// Notes:
//   - Captures the Outlook window region via haijunbot.cap("windows.script.exec", ...), then
//     recognizes text via haijunbot.cap("ocr.recognize", ...).
//   - Actions: list reads the inbox mail list; read clicks a specified mail to read its body
//     (matched by subject substring or list index).
//   - Depends on the gateway OCR (ocr.recognize). The run-script standalone process needs the
//     environment variables HAIJUNBOT_GATEWAY + HAIJUNBOT_AUTH_TOKEN to inject credentials;
//     otherwise OCR returns a clear error.
//   - No credentials are hardcoded.
//
// Caution: the script runs with daemon privileges, equivalent to shell privileges. It only
// performs reads and contains no write operations.

// ---------------------------------------------------------------------------
// Tool: capture the window region (define a complete C# class with Add-Type to avoid
// struct New-Object issues)
// ---------------------------------------------------------------------------
function captureWindowRegion(windowId, outPath) {
  const hex = String(windowId).replace("0x", "");
  const ps = `
Add-Type -AssemblyName System.Drawing
$src = @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public class CapShot {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  public static string Shot(IntPtr h, string path) {
    RECT r; GetWindowRect(h, out r);
    int w = r.Right - r.Left, ht = r.Bottom - r.Top;
    using (Bitmap bmp = new Bitmap(w, ht)) {
      using (Graphics g = Graphics.FromImage(bmp)) { g.CopyFromScreen(r.Left, r.Top, 0, 0, bmp.Size); }
      bmp.Save(path, ImageFormat.Png);
    }
    return r.Left + "," + r.Top + "," + w + "," + ht;
  }
}
'@
Add-Type -TypeDefinition $src -ReferencedAssemblies System.Drawing
[CapShot]::Shot([IntPtr]0x${hex}, '${outPath}')
`;
  const res = haijunbot.cap("windows.script.exec", {
    script: ps,
    interpreter: "powershell",
    timeout_ms: 20000,
  });
  if (!res.success) throw new Error("screenshot failed: " + res.error);
  return res.data && res.data.stdout ? res.data.stdout.trim() : "";
}

// ---------------------------------------------------------------------------
// Tool: OCR recognition (returns { text, lines })
// ---------------------------------------------------------------------------
function ocrImage(path, withDetail) {
  const params = {
    image: path,
    lang: "chi_sim+eng",
    gateway: "https://hjb-ai.cn:4443",
  };
  if (withDetail) params.detail = true;
  const res = haijunbot.cap("ocr.recognize", params);
  if (!res.success) throw new Error("OCR failed: " + res.error);
  const d = res.data || {};
  return { text: d.text || "", lines: d.lines || [] };
}

// ---------------------------------------------------------------------------
// Action 1: list — read the inbox mail list (OCR text)
// ---------------------------------------------------------------------------
function listMails(win) {
  captureWindowRegion(
    win.window_id,
    "C:\\Users\\skyfire\\.haijunbot\\scripts\\olk_cap.png",
  );
  haijunbot.sleep(600);
  const { text } = ocrImage(
    "C:\\Users\\skyfire\\.haijunbot\\scripts\\olk_cap.png",
    false,
  );
  return text;
}

// ---------------------------------------------------------------------------
// Action 2: read — click a specified mail to read its body
//   subject: match the mail row by subject substring; index: match by list row number (0-based)
// ---------------------------------------------------------------------------
function readMail(win, subject, index) {
  // Screenshot + OCR detail to get mail row coordinates
  captureWindowRegion(
    win.window_id,
    "C:\\Users\\skyfire\\.haijunbot\\scripts\\olk_cap.png",
  );
  haijunbot.sleep(600);
  const { text, lines } = ocrImage(
    "C:\\Users\\skyfire\\.haijunbot\\scripts\\olk_cap.png",
    true,
  );

  // Window origin (the screenshot returns "left,top,w,h")
  const rectStr = captureWindowRegion(
    win.window_id,
    "C:\\Users\\skyfire\\.haijunbot\\scripts\\olk_cap.png",
  );
  const parts = rectStr.split(",");
  const ox = parseInt(parts[0], 10);
  const oy = parseInt(parts[1], 10);

  // The mail list is on the left side of the window (approximately the x 98~340 region).
  // Filter the OCR lines in the left region as candidate mail rows.
  // Use the row coordinates from OCR detail, take the center point of each row; match by subject or select by index.
  const leftLines = lines.filter(
    (l) => l.bbox && l.bbox.x < 360 && l.bbox.y > 60,
  );
  // Group by y; lines with close y are treated as the same row
  leftLines.sort((a, b) => a.bbox.y - b.bbox.y);
  const rows = [];
  for (const l of leftLines) {
    const cy = l.bbox.y + l.bbox.height / 2;
    if (rows.length === 0 || Math.abs(rows[rows.length - 1].y - cy) > 18) {
      rows.push({ y: cy, x: l.bbox.x + l.bbox.width / 2, text: l.text });
    } else {
      rows[rows.length - 1].text += " " + l.text;
    }
  }

  // Select the target row
  let target = null;
  if (subject) {
    for (const r of rows) {
      if (r.text.indexOf(subject) >= 0) {
        target = r;
        break;
      }
    }
    if (!target) throw new Error("no mail row found with subject containing '" + subject + "'");
  } else {
    const idx = index !== undefined ? index : 0;
    if (idx < 0 || idx >= rows.length)
      throw new Error("index out of range: " + idx + " (total " + rows.length + " rows)");
    target = rows[idx];
  }

  // Click the row (screen coordinates = window coordinates + window origin)
  const sx = Math.round(ox + target.x);
  const sy = Math.round(oy + target.y);
  const clickRes = haijunbot.cap("windows.input.click", { x: sx, y: sy });
  if (!clickRes.success) throw new Error("click failed: " + clickRes.error);

  // Wait for the body to load, then screenshot + OCR
  haijunbot.sleep(1500);
  captureWindowRegion(
    win.window_id,
    "C:\\Users\\skyfire\\.haijunbot\\scripts\\olk_cap.png",
  );
  haijunbot.sleep(600);
  const body = ocrImage(
    "C:\\Users\\skyfire\\.haijunbot\\scripts\\olk_cap.png",
    false,
  );
  return { clicked: target.text, body: body.text };
}

// ---------------------------------------------------------------------------
// Tool: locate the Outlook Inbox window
// ---------------------------------------------------------------------------
function findOutlookWindow() {
  const res = haijunbot.cap("windows.window.list", {});
  if (!res.success) throw new Error("window.list failed: " + res.error);
  let wins = [];
  if (Array.isArray(res.data)) wins = res.data;
  else if (res.data && Array.isArray(res.data.windows)) wins = res.data.windows;
  else if (res.data && Array.isArray(res.data.result)) wins = res.data.result;
  for (const w of wins) {
    const title = w.title || w.Title || w.name || "";
    if (title.indexOf("Outlook") >= 0 && title.indexOf("Inbox") >= 0) {
      return {
        window_id: w.window_id || w.WindowID,
        title: title,
        pid: w.pid || w.PID,
      };
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Main flow
// ---------------------------------------------------------------------------
const action = haijunbot.args.action || "list";
let result;

const win = findOutlookWindow();
if (!win) {
  throw new Error("Outlook Inbox window not found (please open new Outlook first)");
}
print("Found Outlook window:", win.window_id, win.title);

if (action === "list") {
  const text = listMails(win);
  print("===== Inbox mail list (OCR) =====");
  print(text);
  print("===== Done =====");
  result = { action: "list", window: win.window_id, ocrText: text };
} else if (action === "read") {
  const subject = haijunbot.args.subject || "";
  const indexRaw = haijunbot.args.index;
  const index = indexRaw !== undefined ? parseInt(indexRaw, 10) : undefined;
  if (!subject && (index === undefined || isNaN(index))) {
    throw new Error("read requires --arg subject=<subject substring> or --arg index=<row number>");
  }
  const out = readMail(win, subject, index);
  print("===== Mail clicked =====");
  print(out.clicked);
  print("===== Body (OCR) =====");
  print(out.body);
  print("===== Done =====");
  result = {
    action: "read",
    window: win.window_id,
    clicked: out.clicked,
    body: out.body,
  };
} else {
  throw new Error("unknown action: " + action + " (supports list/read)");
}

result;
