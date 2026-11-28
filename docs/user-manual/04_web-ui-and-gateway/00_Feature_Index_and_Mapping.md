# Web UI and Gateway Feature Index

## Use Cases

When using HaijunBot through a browser, you can start from this index to determine which document covers the feature you need. It is suitable when you are new to the Web UI, preparing to connect to the gateway, or already connected but unsure how to use a particular button or panel.

## Steps

1. First, based on what you want to accomplish, find the closest scenario in the categories below.
2. Then open the matching document and follow its steps.
3. If you are using a phone or a narrow window, pay extra attention to the mobile notes in each document, because the sidebar, terminal panel, and editor render differently than on desktop.
4. If a feature requires you to already be connected to the Web Gateway, complete the following basic steps first:
   - Start the Web Gateway service
   - Connect to the HaijunBot Gateway from the browser
   - Log in with a password if needed

## Feedback You Will See

- The documents in this directory mainly cover the following capabilities:
  - Starting, connecting, and reconnecting
  - Agent management and session restore
  - Input, completion, and manual intervention
  - File tree, editor, and terminal
  - History, settings, and UI experience

- Most documents follow the fixed structure of "Use Cases / Steps / Feedback You Will See / Notes".
- If a capability happens automatically, the document states clearly that you do not need to enter any extra commands.

## Notes

- Many features in the Web UI depend on you having successfully connected to the Gateway; if the top still shows "Not Connected", resolve the connection issue first.
- Some capabilities are more complete on desktop, such as dragging to resize the sidebar and freely resizing the terminal or editor; on mobile they tend to render as full-screen or overlay views.
- If the buttons you see do not match the document, first check whether you are on a different device width, a different Agent state, or whether the current Agent has already finished.

## Document Index

### 1. Startup and Connection

- [Start the Web Gateway Service](./Starting_the_Web_Gateway_Service.md)
- [Connect to the HaijunBot Gateway from the Browser](./Connecting_to_HaijunBot_Gateway_from_the_Browser.md)
- [Log in to the Web Gateway with a Password](./Logging_into_Web_Gateway_with_a_Password.md)
- [Get Started with the Newcomer Guide](./Using_the_Newcomer_Guide_to_Get_Started.md)
- [Open Settings and Manage Connections and History](./Opening_Settings_and_Managing_Connections_and_History.md)
- [Manage History and Reconnect](./Managing_History_and_Reconnecting.md)

### 2. Distributed Deployment

- [Distributed Gateway Deployment Method](./Distributed_Gateway_Deployment_Method.md) - A complete guide to multi-node deployment
- [Node Mode Deployment and Integration Handbook](./Node_Mode_Deployment_and_Integration_Handbook.md)

### 3. Agent Management and Sessions

- [Create a General or Code Agent](./Creating_General_or_Code_Agents.md)
- [View and Switch Agents in the Web UI](./Viewing_and_Switching_Agents_in_the_Web_UI.md)
- [View an Agent's Running Status](./Viewing_Agent_Running_Status.md)
- [View an Agent's Node in the Web UI](./Viewing_an_Agent_Nodes_in_the_Web_UI.md)
- [Duplicate, Rename, and Delete Agents](./Duplicating_Renaming_and_Deleting_Agents.md)
- [Restore Agent Sessions](./Restoring_Agent_Sessions.md)

### 4. Input, Completion, and Manual Intervention

- [Enter Content and Respond to Confirmations in the Web UI](./Entering_Content_and_Responding_to_Confirmations_in_the_Web_UI.md)
- [Manage Input Buffers and History Input](./Managing_Input_Buffers_and_History_Input.md)
- [Insert Common Content with the Completion Panel](./Inserting_Common_Content_with_the_Completion_Panel.md)
- [Intervene While an Agent is Running](./Intervening_While_an_Agent_is_Running.md)

### 5. Terminal, Files, and UI Experience

- [Use the Standalone Terminal Panel](./Using_the_Standalone_Terminal_Panel.md)
- [View Execution Terminal Output in Messages](./Viewing_Terminal_Output_in_Messages.md)
- [Use the Web UI File Tree and Online Editor](./Using_the_File_Tree_and_Online_Editor.md)
- [Adjust the Sidebar and Floating Window Layout](./Adjusting_Sidebar_and_Floating_Window_Layout.md)
- [Edit Config Files in the Web UI](./Editing_Config_Files_in_the_Web_UI.md)
- [View Version and About Info](./Viewing_Version_and_About_Info.md) - View the version, open-source license, and component versions

### 6. Shortcuts, Management Sidebar, and Scheduled Tasks

- [Use Shortcuts for Quick Operations](./Using_Shortcuts_for_Quick_Operations.md) - Space Leader sequences and standard two-key shortcuts
- [Use the Management Sidebar](./Using_the_Management_Sidebar.md) - View scheduled tasks and the enhanced capabilities list
- [Manage Scheduled Tasks and Scheduling](./Managing_Scheduled_Tasks_and_Scheduling.md) - Scheduled task scheduling types and cron expressions
