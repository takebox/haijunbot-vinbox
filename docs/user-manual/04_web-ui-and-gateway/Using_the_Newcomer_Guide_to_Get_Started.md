# Getting Started with the Newcomer Guide

## Use Cases

HaijunBot provides a scenario-based interactive newcomer guide that walks you through the key areas of the interface. It is suitable for new users who have just deployed HaijunBot and have not created an Agent yet, or who are connected but do not know where to start.

The guide is not shown all at once; it is **split by scenario**: it only appears automatically when you enter a scenario whose guide you have not seen yet. If you are already familiar with the interface, you can skip it anytime; to view it again later, you can reopen it from the command palette.

## Steps

1. Log in to the Web Gateway with a password (or auto-connect with saved credentials).
2. The **welcome guide** does not pop up automatically: when there are no Agents yet, an empty-state card appears in the center of the pet hall; click "View getting-started guide" in it to open it. You can also press `Ctrl+P` to open the command palette and search for "View HaijunBot Intro" to open it anytime. When the guide appears, the rest of the interface is dimmed, and the currently explained button or area is highlighted.
3. Read the explanation in the bubble and click "Next" to continue; you can also click "Back" to review.
4. The guide has 5 scenarios in total, each triggered at its own moment; clicking "Start Using" at the last step of each scenario completes that scenario's guide.

| Scenario      | Steps | Trigger timing                                        |
| ------------- | ----- | ----------------------------------------------------- |
| Welcome guide | 6     | Opened via the empty-state card's "View getting-started guide" or the command palette's "View HaijunBot Intro" |
| Lobby guide   | 8     | When no panel is open and you stay on the pet hall    |
| Agent guide   | 4     | After the first Agent is created                      |
| Panel guide   | 6     | After opening an Agent's conversation panel for the first time |
| Sidebar guide | 4     | After opening the Agent sidebar for the first time    |

Each scenario roughly covers:

- **Welcome guide**: HaijunBot's core concept - driving multiple Agents to work together at the same time; the five core concepts (Agent, node, gateway, pet hall, command palette); the entries in the top-right toolbar; grouping, searching, and executing in the command palette; more entries such as hiding the pet, logging out, and the management panel; how to create the first Agent and start a conversation.
- **Lobby guide**: the lobby dashboard (time, connection status, gateway address, node and Agent statistics); pets are Agents (drag, double-click to open a panel); using @ references in the pet input box; nodes and topology; creating an Agent; one-sentence Agent creation (⚡ floating button); the pet's right-click menu; the node's right-click menu.
- **Agent guide**: the meaning of Agent status colors; the Agent sidebar; managing a single Agent (rename/duplicate/permission management/lossless regeneration/delete/manual intervention); custom groups.
- **Panel guide**: chatting in a panel; quick references with @; confirmation cards; the panel's right-click menu; detaching and closing; auto-scroll and auto-read aloud.
- **Sidebar guide**: the Agent list; the Agent's right-click menu; bulk operations; managing groups.

### Skipping and Re-watching

- Click the `✕` at the top-right of the bubble, "Skip Guide" at the bottom, or press `Esc` directly to exit the current scenario's guide at any time.
- Whether completed or skipped, HaijunBot remembers that this scenario has been seen, and it will not pop up again automatically.
- To re-watch it, press `Ctrl+P` to open the command palette and search for keywords such as "guide", "tutorial", or "help"; you can run:
  - **View HaijunBot Intro**: reopen the welcome guide.
  - **View Sidebar Guide**: reopen the sidebar guide.
  - **Reset Newcomer Guide**: clear the "seen" marks of all scenarios, and the guides will trigger again automatically when you enter the corresponding scenarios.

### Empty-State Guide When There Are No Agents

If there are no Agents yet, an empty-state card appears in the center of the pet hall with two buttons:

- **Create the First Agent**: open the creation window directly on the first online node.
- **View Getting-Started Guide**: reopen the welcome guide.

### Documentation Entry

You can consult the full documentation at any time by:

- Clicking the **❓** button in the top-right toolbar (its hover tooltip is "Documentation").
- Or searching for and running **Open Documentation** in the command palette (`Ctrl+P`) (shortcut `Ctrl+Alt+Shift+H`).

Clicking opens the official HaijunBot documentation site (<https://takebox.github.io/HaijunBot/>) in a new tab without affecting the current interface.

## Feedback You Will See

- When the guide appears, the explained button or area is outlined in cyan, and the rest is darkened by a semi-transparent overlay.
- Above the bubble, the step title and progress are shown (e.g. `3 / 6`), and below it a row of dots shows the current progress.
- If the element a step wants to explain is not currently on the interface (e.g. no Agent panel is open), that step degrades gracefully to a card in the center of the screen instead of getting stuck.
- After completing the **welcome guide**, a success message "Guide completed, start using HaijunBot" pops up at the bottom-right.
- In the login window, the username defaults to `admin`, and there is no extra hint below the password input; how to obtain the initial admin password is explained in step 5 of the "Quick Start: Installation and Deployment" panel in the login window (on first startup a random password is generated and printed to the service log).

## Notes

- The guide is only an overlay on the interface; it does not modify any Agent state or config, and exiting it at any time does not affect running tasks.
- When using the keyboard in the guide: `Esc` skips, and `←` / `→` switch between the previous/next step.
- The "guide seen" marks are stored in the browser's local storage, with the key format `haijunbot_onboarding_{scenario}_v1` (e.g. `haijunbot_onboarding_welcome_v1` for the welcome guide); older versions used a single key `haijunbot_onboarding_done_v1`, which now serves as a legacy compatibility mark for the welcome guide. After clearing browser data, switching browsers, or using an incognito window, the guides appear automatically again.
- If your login credential expires while the guide is displayed and you return to the connection dialog, the guide overlay is covered by the connection dialog (but not closed automatically); after logging in again, the guide continues from where it was.
- On first use, be sure to change the initial admin password under "Settings → Change Password".
