# Using the Web UI File Tree and Online Editor

## Use Cases

When you want to browse the Agent's working directory, open files, view content, and edit online directly in the HaijunBot web interface, you can use the file tree and the floating editor without switching back to a local terminal or an external editor.

## Steps

### Browsing the File Tree

1. First select a connected Agent.
2. In the Agent list on the left, click the working directory text of that Agent.
3. After clicking, the Agent's file tree loads and expands automatically; if the directory is empty, it shows "No content to display in the current working directory".
4. Click a directory in the file tree to expand or collapse its sub-items.
5. Clicking a file opens it directly in the editor.

### Opening and Viewing a File

1. Click a file in the file tree.
2. The page automatically opens the "Editor" floating panel.
3. If this file was already opened, the page switches to the existing tab.
4. If it is a new file, a new tab is created and the current file path is shown.

### Switching between Read-Only and Editable Modes

1. After opening the editor, check the lock state in the toolbar at the top.
2. By default, the editor is in read-only mode.
3. Click the toggle button to switch between "Read-only" and "Editable".

### Saving a File

1. First switch to editable mode.
2. Modify the file content.
3. Click the save button.
4. After a successful save, the toolbar state updates and a success message appears.

### Closing a Tab or Closing the Editor

1. To close a single file tab, click the close button on the tab.
2. To close the entire editor panel, click the close button at the top-right of the editor panel.
3. If there are unsaved changes, the system shows a confirmation prompt first.

## Feedback You Will See

- In the file tree, directories and files are shown with different icons.
- When the editor has no file open, it shows "Click a file in the file tree to open the code editor".
- The editor toolbar shows:
  - Loading
  - Error information
  - Saved
  - Unsaved changes

- After a successful save, you will see a "File saved" message.
- If the file was modified externally:
  - If there are no unsaved changes, the page refreshes to the latest content automatically
  - If there are unsaved changes, the page warns about external changes to avoid silent overwrites

- If you close an unsaved tab or close the whole editor, the page asks for confirmation first.

## Notes

- The editor is read-only by default; you need to switch to editable mode manually before modifying files.
- Not every file can be opened and edited; the web editor only suits text files.
- Files that are too large, not plain text, or do not meet the read conditions may not open properly in the web page.
- The editor supports multiple tabs, window dragging, resizing, maximizing, and restoring; on mobile it is closer to a full-screen presentation.
