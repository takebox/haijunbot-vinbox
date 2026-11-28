// outlook.js — operates desktop Outlook via Outlook COM (background service script)
//
// Usage (on Windows; the daemon must support run-script):
//   haijunbot-daemon run-script examples/outlook.js --arg action=list
//   haijunbot-daemon run-script examples/outlook.js --arg action=list --arg filter=Wang
//   haijunbot-daemon run-script examples/outlook.js --arg action=read --arg id=<entryid>
//   haijunbot-daemon run-script examples/outlook.js --arg action=search --arg query=invoice
//   haijunbot-daemon run-script examples/outlook.js --arg action=send \
//       --arg to=a@b.com --arg subject=Title --arg body=Body
//
// Notes:
//   - Executes PowerShell COM operations on Outlook via haijunbot.cap("windows.script.exec", ...).
//   - Actions: list lists inbox mails (can filter sender/subject by filter); read reads a
//     specified mail's body; search searches mails; send sends a mail.
//   - No credentials are hardcoded; sending mails relies on the account already configured in Outlook.
//
// Caution: the script runs with daemon privileges, equivalent to shell privileges. send is a
// write operation; confirm your intent before using it.

// ---------------------------------------------------------------------------
// PowerShell common snippet: starts Outlook COM and returns the Mail object
// ---------------------------------------------------------------------------
// Invoke PowerShell in single-line mode to avoid escaping hell: pass the PowerShell code as the
// script body to windows.script.exec, which the daemon executes via powershell -Command.

function psExec(powershellCode) {
  const res = haijunbot.cap("windows.script.exec", {
    script: powershellCode,
    interpreter: "powershell",
    timeout_ms: 60000,
  });
  if (!res.success) {
    console.error("failed to execute PowerShell:", res.error);
    throw new Error("PowerShell execution failed: " + res.error);
  }
  return res.data;
}

// Extract JSON from the PowerShell output (the script outputs with ConvertTo-Json -Compress at the end)
function extractJson(raw) {
  if (!raw || !raw.stdout) return null;
  const s = raw.stdout.trim();
  const start = s.indexOf("{");
  const end = s.lastIndexOf("}");
  if (start < 0 || end < 0 || end <= start) return null;
  const json = s.slice(start, end + 1);
  try {
    return JSON.parse(json);
  } catch (e) {
    console.error("failed to parse JSON:", e.message);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Action 1: list — list inbox mails (supports filtering sender/subject by filter)
// ---------------------------------------------------------------------------
function listMails(filter) {
  const ps = `
$ErrorActionPreference = 'Stop'
try {
  $ol = New-Object -ComObject Outlook.Application
  $ns = $ol.GetNamespace('MAPI')
  $inbox = $ns.GetDefaultFolder(6)  # 6 = olFolderInbox
  $items = $inbox.Items
  $result = @()
  foreach ($m in $items) {
    if ($m.Class -ne 43) { continue }  # 43 = olMail
    $sender = ''
    try { $sender = $m.SenderName } catch {}
    $subject = ''
    try { $subject = $m.Subject } catch {}
    $filter = '${filter}'
    if ($filter -ne '' -and $subject -notlike "*$filter*" -and $sender -notlike "*$filter*") { continue }
    $result += [PSCustomObject]@{
      id      = $m.EntryID
      sender  = $sender
      subject = $subject
      time    = $m.ReceivedTime.ToString('yyyy-MM-dd HH:mm')
      unread  = $m.UnRead
    }
  }
  $result | ConvertTo-Json -Compress -Depth 3
} catch {
  Write-Output ('ERROR: ' + $_.Exception.Message)
  exit 1
}
`;
  const data = psExec(ps);
  const json = extractJson(data);
  if (!json) {
    // May output ERROR or empty
    const raw = data && data.stdout ? data.stdout.trim() : "";
    if (raw.indexOf("ERROR:") === 0) {
      throw new Error("Outlook list failed: " + raw);
    }
    return [];
  }
  // ConvertTo-Json outputs an object for a single item and an array for multiple items
  return Array.isArray(json) ? json : [json];
}

// ---------------------------------------------------------------------------
// Action 2: read — read a specified mail's body
// ---------------------------------------------------------------------------
function readMail(entryId) {
  const ps = `
$ErrorActionPreference = 'Stop'
try {
  $ol = New-Object -ComObject Outlook.Application
  $ns = $ol.GetNamespace('MAPI')
  $mail = $ns.GetItemFromID('${entryId}')
  $body = ''
  try { $body = $mail.Body } catch {}
  [PSCustomObject]@{
    id      = $mail.EntryID
    sender  = $mail.SenderName
    subject = $mail.Subject
    time    = $mail.ReceivedTime.ToString('yyyy-MM-dd HH:mm')
    body    = $body
  } | ConvertTo-Json -Compress -Depth 3
} catch {
  Write-Output ('ERROR: ' + $_.Exception.Message)
  exit 1
}
`;
  const data = psExec(ps);
  const json = extractJson(data);
  if (!json) {
    const raw = data && data.stdout ? data.stdout.trim() : "";
    if (raw.indexOf("ERROR:") === 0)
      throw new Error("Outlook read failed: " + raw);
    throw new Error("Outlook read failed: unable to parse result");
  }
  return json;
}

// ---------------------------------------------------------------------------
// Action 3: search — search mails (by subject/body keywords)
// ---------------------------------------------------------------------------
function searchMails(query) {
  const ps = `
$ErrorActionPreference = 'Stop'
try {
  $ol = New-Object -ComObject Outlook.Application
  $ns = $ol.GetNamespace('MAPI')
  $inbox = $ns.GetDefaultFolder(6)
  $items = $inbox.Items
  $result = @()
  $q = '${query}'
  foreach ($m in $items) {
    if ($m.Class -ne 43) { continue }
    $subject = ''
    $body = ''
    try { $subject = $m.Subject } catch {}
    try { $body = $m.Body } catch {}
    if ($subject -like "*$q*" -or $body -like "*$q*") {
      $result += [PSCustomObject]@{
        id      = $m.EntryID
        sender  = $m.SenderName
        subject = $subject
        time    = $m.ReceivedTime.ToString('yyyy-MM-dd HH:mm')
      }
    }
  }
  $result | ConvertTo-Json -Compress -Depth 3
} catch {
  Write-Output ('ERROR: ' + $_.Exception.Message)
  exit 1
}
`;
  const data = psExec(ps);
  const json = extractJson(data);
  if (!json) {
    const raw = data && data.stdout ? data.stdout.trim() : "";
    if (raw.indexOf("ERROR:") === 0)
      throw new Error("Outlook search failed: " + raw);
    return [];
  }
  return Array.isArray(json) ? json : [json];
}

// ---------------------------------------------------------------------------
// Action 4: send — send a mail
// ---------------------------------------------------------------------------
function sendMail(to, cc, subject, body) {
  const ps = `
$ErrorActionPreference = 'Stop'
try {
  $ol = New-Object -ComObject Outlook.Application
  $mail = $ol.CreateItem(0)  # 0 = olMailItem
  $mail.To = '${to}'
  if ('${cc}' -ne '') { $mail.CC = '${cc}' }
  $mail.Subject = '${subject}'
  $mail.Body = '${body}'
  $mail.Send()
  Write-Output ('SENT: ' + $mail.Subject)
} catch {
  Write-Output ('ERROR: ' + $_.Exception.Message)
  exit 1
}
`;
  const data = psExec(ps);
  const raw = data && data.stdout ? data.stdout.trim() : "";
  if (raw.indexOf("SENT:") === 0) {
    return { ok: true, subject: raw.slice(6) };
  }
  if (raw.indexOf("ERROR:") === 0) {
    throw new Error("Outlook send failed: " + raw);
  }
  throw new Error("Outlook send failed: unknown result");
}

// ---------------------------------------------------------------------------
// Main flow
// ---------------------------------------------------------------------------
const action = haijunbot.args.action || "list";
let result;

if (action === "list") {
  const filter = haijunbot.args.filter || "";
  const mails = listMails(filter);
  print("Inbox mail count:", mails.length);
  for (const m of mails) {
    print(
      (m.unread ? "[Unread] " : "      ") +
        m.time +
        "  " +
        m.sender +
        "  " +
        m.subject,
    );
  }
  result = { action: "list", count: mails.length, mails: mails };
} else if (action === "read") {
  const id = haijunbot.args.id;
  if (!id) throw new Error("read requires --arg id=<entryid>");
  const mail = readMail(id);
  print("Sender:", mail.sender);
  print("Subject:", mail.subject);
  print("Time:", mail.time);
  print("----------------------------------------");
  print(mail.body);
  result = { action: "read", mail: mail };
} else if (action === "search") {
  const query = haijunbot.args.query || "";
  if (!query) throw new Error("search requires --arg query=<keyword>");
  const mails = searchMails(query);
  print("Mails found:", mails.length);
  for (const m of mails) {
    print(m.time + "  " + m.sender + "  " + m.subject);
  }
  result = {
    action: "search",
    query: query,
    count: mails.length,
    mails: mails,
  };
} else if (action === "send") {
  const to = haijunbot.args.to;
  if (!to) throw new Error("send requires --arg to=<recipient>");
  const subject = haijunbot.args.subject || "";
  const body = haijunbot.args.body || "";
  const cc = haijunbot.args.cc || "";
  result = sendMail(to, cc, subject, body);
  print("Sent:", result.subject);
} else {
  throw new Error("unknown action: " + action + " (supports list/read/search/send)");
}

result;
