// outlook_ui_test.js — verifies the UI mode chain (screenshot + OCR to read the new Outlook mail list)
// Usage: haijunbot-daemon run-script outlook_ui_test.js

// 1. Find the Outlook window (the new Outlook, olk.exe)
function findOutlookWindow() {
  const res = haijunbot.cap("windows.window.list", {});
  if (!res.success) throw new Error("window.list failed: " + res.error);
  print(
    "window.list res.data type:",
    typeof res.data,
    JSON.stringify(res.data).slice(0, 300),
  );
  // Compatible with both structures: res.data is an array directly, or res.data.windows is an array
  let wins = [];
  if (Array.isArray(res.data)) wins = res.data;
  else if (res.data && Array.isArray(res.data.windows)) wins = res.data.windows;
  else if (res.data && Array.isArray(res.data.result)) wins = res.data.result;
  for (const w of wins) {
    const title = w.title || w.Title || w.name || "";
    if (title.indexOf("Outlook") >= 0 && title.indexOf("Inbox") >= 0) {
      // Return lowercase fields uniformly
      return {
        window_id: w.window_id || w.WindowID,
        title: title,
        pid: w.pid || w.PID,
      };
    }
  }
  return null;
}

// 2. Minimize windows that may be in the way and focus Outlook
function ensureOutlookVisible(win) {
  // Use PowerShell to bring the Outlook window to the front + minimize other visible windows
  const ps = `
Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class UIV{ [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int c); [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);}'
$h = [IntPtr]0x${win.window_id.replace("0x", "")}
[UIV]::ShowWindow($h, 9) | Out-Null   # SW_RESTORE
[UIV]::BringWindowToTop($h) | Out-Null
[UIV]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 800
Write-Output 'OK'
`;
  const res = haijunbot.cap("windows.script.exec", {
    script: ps,
    interpreter: "powershell",
    timeout_ms: 15000,
  });
  if (!res.success) throw new Error("failed to focus Outlook: " + res.error);
  return true;
}

// 3. Capture the Outlook window region
function captureOutlookRegion(win) {
  const ps = `
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class UIV2{ [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r); public struct RECT{public int Left,Top,Right,Bottom;} }'
$r = New-Object UIV2+RECT
[UIV2]::GetWindowRect([IntPtr]0x${win.window_id.replace("0x", "")}, [ref]$r) | Out-Null
$x = $r.Left; $y = $r.Top; $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($x, $y, 0, 0, $bmp.Size)
$bmp.Save('C:\\Users\\skyfire\\.haijunbot\\scripts\\olk_cap.png', [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output ('OK ' + $x + ' ' + $y + ' ' + $w + ' ' + $h)
`;
  const res = haijunbot.cap("windows.script.exec", {
    script: ps,
    interpreter: "powershell",
    timeout_ms: 20000,
  });
  if (!res.success) throw new Error("screenshot failed: " + res.error);
  return "C:\\Users\\skyfire\\.haijunbot\\scripts\\olk_cap.png";
}

// 4. OCR recognition
function ocrImage(path) {
  const res = haijunbot.cap("ocr.recognize", {
    image: path,
    lang: "chi_sim+eng",
    gateway: "https://hjb-ai.cn:4443",
  });
  if (!res.success) throw new Error("OCR failed: " + res.error);
  return res.data && res.data.text ? res.data.text : "";
}

// Main flow
let result;
const win = findOutlookWindow();
if (!win) {
  throw new Error("Outlook Inbox window not found");
}
print("Found Outlook window:", win.window_id, win.title);
ensureOutlookVisible(win);
haijunbot.sleep(1000);
const shot = captureOutlookRegion(win);
print("Screenshot saved:", shot);
const text = ocrImage(shot);
print("===== OCR recognition result =====");
print(text);
print("===== Done =====");
result = { ok: true, window: win.window_id, ocrText: text };
result;
