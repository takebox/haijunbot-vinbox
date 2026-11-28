# Using the Standalone Terminal Panel

## Use Cases

When you want to keep one or more standalone terminals in the Web UI to run extra commands, view output, or work in parallel with the message area, you can use the standalone terminal panel instead of relying only on the embedded execution output inside Agent tasks.

## Steps

1. First make sure the current page is already connected to the Web Gateway.
2. Click the "Terminal Panel" button at the top or in the mobile toolbar.
3. After opening the terminal panel, if there is no terminal yet, you will see "No terminal yet, click + to create".
4. Click the "+" button in the terminal panel to create a new terminal.
5. After creation, the page switches to this new terminal tab automatically.
6. If there are already multiple terminals, click different tabs to switch between them.
7. To close a terminal, click the close button on the corresponding tab.
8. To hide the terminal panel temporarily, click the close button at the top-right of the terminal panel; when you open it again later, the existing terminal content can be restored and shown.

## Feedback You Will See

- After opening the terminal panel, the panel title shows "Terminal".
- After creating a new terminal, a new terminal tab appears.
- The terminal tab shows the current interpreter name.
- In the terminal panel, output can be seen in real time.
- If a terminal has been closed, the page removes the corresponding tab accordingly, instead of keeping an invalid session indefinitely.

## Notes

- The standalone terminal panel and the execution terminal in the message area are not the same thing; this is a terminal panel you can keep separately and switch between multiple tabs.
- If the main connection drops, the page cleans up the standalone terminal sessions, so you need to restore the gateway connection before continuing to use it.
- The terminal panel supports dragging, resizing, maximizing, and restoring; mobile and desktop render it differently.
- The backend limits the number of standalone terminal sessions, so creating new terminals without limit is not supported.
