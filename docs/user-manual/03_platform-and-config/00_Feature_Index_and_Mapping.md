# Feature Index and Mapping Notes

## Use Cases

If you want to quickly confirm which features each official document in the "Platform and Config" directory covers, or verify whether the 44 feature points in the draft have made it into the official documents, you can start with this index.

## Steps

1. First, based on the problem you want to solve, find the corresponding number in the "Feature Mapping Table" below.
2. Look at the official document name listed after that number.
3. If a number corresponds to one document, go directly to that document to proceed.
4. If multiple numbers share the same document, it means these features are consecutive sub-steps within the same entry point, and the official manual uses a "merged coverage" approach.

## Prompts and Feedback You Will See

- Most feature points already have their own standalone official document.
- A few feature points are merged into the same document to avoid splitting a continuous interaction flow too finely.
- There are 42 official feature documents in this directory, of which 40 are covered by this mapping table (the 44 draft feature points correspond to these 40 after "merged coverage"); the difference mainly comes from "merged coverage" rather than missing documents.
- Another 2 official feature documents (Connecting the Jev TypeSafe Platform and Configuring the Structured Evaluation Model) are not among the original 44 draft feature points and are listed as "supplementary" entries at the end of this table.

## Notes

- This is an index document and does not replace the specific operation manuals themselves.
- If you find that an official document title for a feature point does not exactly match the draft title, judge by whether the behavior is actually covered rather than by literal title matching.
- For capabilities that are not yet stably exposed as independent config options in the current source code, the official document explicitly writes them as a "current behavior description" rather than mistakenly describing them as stable config switches.

## Feature Mapping Table

| Draft No. | Feature Point                                                                     | Official Document                                                |
| --------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| 1         | How to quickly configure the OpenAI or Haijun platform                            | `Quickly_Configuring_OpenAI_or_Haijun_Platforms.md`              |
| 2         | How to automatically fetch the list of available models and choose which to configure | `Quickly_Configuring_OpenAI_or_Haijun_Platforms.md`          |
| 3         | How to manually enter a model name when quick configuration fails                  | `Quickly_Configuring_OpenAI_or_Haijun_Platforms.md`              |
| 4         | How to choose the normal, smart, and cheap models for a model group                | `Quickly_Configuring_OpenAI_or_Haijun_Platforms.md`              |
| 5         | How to test model API connectivity before saving the configuration                 | `Quickly_Configuring_OpenAI_or_Haijun_Platforms.md`              |
| 6         | How to view, add, update, and delete LLM configurations in the platform manager    | `Managing_LLM_Configuration.md`                                  |
| 7         | How to view, add, update, delete, and switch model groups in the platform manager  | `Managing_Model_Groups_and_Setting_the_Default.md`               |
| 8         | How to view current platform and model information                                | `Viewing_Current_Platform_and_Model_Info.md`                     |
| 9         | How to chat directly with the current model                                       | `Talking_Directly_to_the_Current_Model.md`                       |
| 10        | How to start an OpenAI-compatible API service                                     | `Starting_an_OpenAI-Compatible_API_Service.md`                   |
| 11        | How to load a role configuration and start a conversation by role                  | `Starting_Conversations_by_Role_Config.md`                       |
| 12        | How to launch the JSON Schema-based Web config UI                                  | `Editing_Config_in_the_Web_Config_UI.md`                         |
| 13        | How to customize the Git commit message generation template                        | `Customizing_Git_Commit_Message_Templates.md`                    |
| 14        | How to configure custom input tags and text replacement rules                       | `Configuring_Custom_Input_Tags_and_Text_Replacements.md`         |
| 15        | How to configure the submit shortcut for multiline input                           | `Configuring_Submit_Shortcuts_for_Multiline_Input.md`            |
| 16        | How to configure the rules auto-loaded by default                                  | `Configuring_Default_Auto-Loaded_Rules.md`                       |
| 17        | How to configure extra rule load directories                                       | `Configuring_Extra_Rule_Load_Directories.md`                     |
| 18        | How to configure the central rules repository                                      | `Configuring_the_Central_Rules_Repository.md`                    |
| 19        | How to configure extra tool load directories                                       | `Configuring_Extra_Tool_Load_Directories.md`                     |
| 20        | How to limit available tools via tool whitelist and blacklist                      | `Limiting_Tools_via_Whitelist_and_Blacklist.md`                  |
| 21        | How to configure the central tool repository                                       | `Configuring_the_Central_Tool_Repository.md`                     |
| 22        | How to connect external tools via MCP configuration                                | `Connecting_External_Tools_via_MCP_Config.md`                    |
| 23        | How to configure extra methodology load directories                                | `Configuring_Extra_Methodology_Load_Directories.md`              |
| 24        | How to configure the central methodology repository                                | `Configuring_the_Central_Methodology_Repository.md`              |
| 25        | How to configure extra Agent definition directories                                | `Configuring_Extra_Agent_Definition_Directories.md`              |
| 26        | How to configure extra role directories                                            | `Configuring_Extra_Role_Directories.md`                          |
| 27        | How to configure custom callback directories after tool calls                      | `Configuring_Custom_Callback_Dirs_After_Tool_Calls.md`           |
| 28        | How to skip predefined task selection at startup                                   | `Skipping_Predefined_Task_Selection_at_Startup.md`               |
| 29        | How to enable CodeAgent auto-restore of historical sessions                        | `Enabling_CodeAgent_Auto-Restore_of_Sessions.md`                 |
| 30        | How to enable or disable build verification after code changes                      | `Enabling_or_Disabling_Build_Verification_After_Edits.md`        |
| 31        | How to adjust the build verification timeout                                       | `Adjusting_Build_Verification_Timeout.md`                        |
| 32        | How to enable or disable code change impact analysis                               | `Enabling_or_Disabling_Change_Impact_Analysis.md`                |
| 33        | How to adjust the code diff display mode                                           | `Adjusting_diff_Display_Mode.md`                                 |
| 34        | How to control whether diff shows line numbers                                     | `Controlling_Whether_diff_Shows_Line_Numbers.md`                 |
| 35        | How to adjust the display threshold for large-file diffs                           | `Adjusting_Large-File_diff_Thresholds.md`                        |
| 36        | How to configure the gateway auth password and access policy when no password is set | `Configuring_Gateway_Password_and_Policy_When_Unset.md`        |
| 37        | How to enable confirmation before tool execution                                   | `Enabling_Confirmation_Before_Tool_Execution.md`                 |
| 38        | How to enable automatic methodology extraction after task completion               | `Enabling_Auto_Methodology_Extraction_After_Tasks.md`            |
| 39        | How to enable automatic memory organization                                        | `Enabling_Auto_Memory_Organization.md`                           |
| 40        | How to enable smart enhancement capabilities (such as proactive interaction and ambiguity handling) | `Enabling_Smart_Enhancement_Capabilities.md`      |
| 41        | How to enable session history saving                                               | `Enabling_Session_History_Saving.md`                             |
| 42        | How to extend available platform implementations and let the system discover them  | `Extending_Platforms_and_Letting_the_System_Discover_Them.md`    |
| 43        | How to view available resource stats at startup (methodologies, tools, memory)     | `Viewing_Available_Resource_Stats_at_Startup.md`                 |
| 44        | How to automatically filter relevant methodologies based on current needs          | `Auto-Filtering_Relevant_Methodology_by_Current_Needs.md`        |
| 45        | How to connect the Jev TypeSafe platform (supplementary, not among the 44 draft items) | `Connecting_the_Jev_TypeSafe_Platform.md`                    |
| 46        | How to configure the structured evaluation model (supplementary, not among the 44 draft items) | `Configuring_the_Structured_Evaluation_Model.md`        |
