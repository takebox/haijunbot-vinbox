# -*- coding: utf-8 -*-
"""Prompt construction module"""

from haijunbot.haijunbot_utils.tag import ot


def build_summary_prompt() -> str:
    """
    Build the summary prompt: require JSON output wrapped in <REPORT>...</REPORT> (JSON only).
    The system prompt does not enforce the main conversation output format; it only gives the structured result in the summary.
    """
    return """
For this round's "security subtask (single-point verification)" structured result, write it only within the markers below, output in the form of a JSON array of objects.
Output only the global number (gid) and detailed reasoning (without location information); gid is a globally unique number.

Example 1: Warning present (has_risk: true, single gid)
<REPORT>
[
  {
    "gid": 1,
    "has_risk": true,
    "preconditions": "The length of the input string src is not less than the size of the dst buffer",
    "trigger_path": "Call path: main() -> handle_network_request() -> parse_packet() -> foobar() -> strcpy(); parse_packet() does not validate the length and directly passes src to foobar(); foobar() calls strcpy(dst, src) without checking the src length, which may cause a buffer overflow. Key call site: parse_packet() does not validate the input length.",
    "consequences": "Buffer overflow, which may cause the program to crash or arbitrary code execution",
    "suggestions": "Use strncpy_s or another safe string copy function"
  }
]
</REPORT>

Example 2: Warning present (has_risk: true, multiple gids merged, path and reasoning identical)
<REPORT>
[
  {
    "gids": [1, 2, 3],
    "has_risk": true,
    "preconditions": "The length of the input string src is not less than the size of the dst buffer",
    "trigger_path": "Call path: main() -> handle_network_request() -> parse_packet() -> foobar() -> strcpy(); parse_packet() does not validate the length and directly passes src to foobar(); foobar() calls strcpy(dst, src) without checking the src length, which may cause a buffer overflow. Key call site: parse_packet() does not validate the input length.",
    "consequences": "Buffer overflow, which may cause the program to crash or arbitrary code execution",
    "suggestions": "Use strncpy_s or another safe string copy function"
  }
]
</REPORT>

Example 3: False positive or no issues (return an empty array)
<REPORT>
[]
</REPORT>

Requirements:
- Output the JSON array only between <REPORT> and </REPORT>; do not mix in any other text.
- If you confirm that this entire batch is all false positives or has no issues, return an empty array [].
- Array elements are objects containing the following fields:
  - gid: integer (globally unique; used for a single warning)
  - gids: integer array (globally unique; used when merging multiple warnings)
  - has_risk: boolean (true/false), indicating whether this item has a real security risk.
  - preconditions: string (the precondition for triggering the vulnerability; required only when has_risk is true)
  - trigger_path: string (the vulnerability trigger path; must include a complete call path derivation: 1) the source of the controllable input; 2) the complete call chain from the input source to the defective code (the function call sequence); 3) the data validation status at each call site; 4) the trigger condition. Format example: "Call path derivation: function A() -> function B() -> function C() -> defective code. Data flow: input source -> propagation path. Key call site: function B() performs no validation.", required only when has_risk is true)
  - consequences: string (the possible consequences after the vulnerability is triggered; required only when has_risk is true)
  - suggestions: string (remediation or mitigation suggestions; required only when has_risk is true)
- **Merge optimization**: If the path (trigger_path) and reasoning (preconditions/consequences/suggestions) of multiple warnings (gid) are exactly the same, you may merge them using a gids array to reduce duplication. Use gid for a single warning and gids for merging multiple warnings. gid and gids cannot appear at the same time.
- Do not mix location information such as file/line/pattern into the array elements; when writing jsonl, the system will automatically merge the original candidates.
- **Key**: Only those with `has_risk` set to `true` are recorded as confirmed issues. For those confirmed to be false positives, set `has_risk` to `false` or do not output that entry.
- **Output format**: Entries with a warning must contain all fields (gid or gids, has_risk, preconditions, trigger_path, consequences, suggestions); entries without a warning contain only gid and has_risk.
- **Call path derivation requirement**: trigger_path must contain a complete call path derivation and must not be omitted or simplified. It must describe the complete call chain from the controllable input to the defective code, as well as the validation status at each call site. If a complete call path cannot be derived, it should be judged a false positive (has_risk: false).
""".strip()


def build_verification_summary_prompt() -> str:
    """
    Build the summary prompt for the verification Agent: verify whether the conclusions given by the analysis Agent are correct.
    """
    return """
For this round's "verification of analysis conclusions" structured result, write it only within the markers below, output in the form of a JSON array of objects.
You need to verify whether the conclusions given by the analysis Agent are correct, including whether the preconditions, trigger path, consequences, and suggestions are reasonable.

Example 1: Verification passed (is_valid: true, single gid)
<REPORT>
[
  {
    "gid": 1,
    "is_valid": true,
    "verification_notes": "The analysis conclusion is correct, the preconditions are reasonable, the trigger path is clear, and the consequence assessment is accurate"
  }
]
</REPORT>

Example 2: Verification passed (is_valid: true, multiple gids merged)
<REPORT>
[
  {
    "gids": [1, 2, 3],
    "is_valid": true,
    "verification_notes": "The analysis conclusion is correct, the preconditions are reasonable, the trigger path is clear, and the consequence assessment is accurate"
  }
]
</REPORT>

Example 3: Verification failed (is_valid: false)
<REPORT>
[
  {
    "gid": 1,
    "is_valid": false,
    "verification_notes": "The preconditions are too broad, the actual code already has input validation, and the trigger path does not hold"
  }
]
</REPORT>

Requirements:
- Output the JSON array only between <REPORT> and </REPORT>; do not mix in any other text.
- Array elements are objects containing the following fields:
  - gid: integer (globally unique; corresponds to the gid given by the analysis Agent; used for a single warning)
  - gids: integer array (globally unique; corresponds to the gids given by the analysis Agent; used when merging multiple warnings)
  - is_valid: boolean (true/false), indicating whether the analysis Agent's conclusion is correct
  - verification_notes: string (verification explanation, explaining why it is correct or incorrect)
- **Merge optimization**: If the verification results (is_valid) and verification explanations (verification_notes) of multiple warnings (gid) are exactly the same, you may merge them using a gids array to reduce duplication. Use gid for a single warning and gids for merging multiple warnings. gid and gids cannot appear at the same time.
- You must verify all input gids and must not omit any.
- If verification passes (is_valid: true), keep the warning; if it does not pass (is_valid: false), treat it as a false positive and do not record it as an issue.
""".strip()


def get_review_system_prompt() -> str:
    """Get the system prompt of the review Agent"""
    return f"""
# Review Agent constraints
- Your main task is to review the conclusions that the clustering Agent judged as invalid, and check whether they are sufficient and correct.
- You must carefully check whether the invalid_reason given by the clustering Agent is sufficient and whether it truly considered all possible paths.
- Tools first: use read_code to read the source code near the target file (about ~50 lines before and after the line number); when necessary, use execute_script to assist with checking.
- When necessary, trace upward to the callers and examine the complete call path to judge whether the clustering Agent's conclusion holds.
- It is forbidden to modify any file or execute write operations; only read-only analysis and reading are allowed.
- Perform only one operation at a time; wait for the tool to return the result before continuing.
- **Memory usage**:
  - During the review, make good use of the memory tool (action=retrieve) to retrieve existing memories, especially those related to the current file or function.
  - Such memories may include function analysis key points, pointer null checks, input validation, call path analysis, etc.
- **Review principles**:
  - You must verify whether the clustering Agent actually checked the various call paths and callers.
  - You must verify whether the clustering Agent actually confirmed that every path has protection.
  - If you find that the clustering Agent omitted a certain path, a certain caller, or a certain edge case, you must judge its reasoning insufficient.
  - Conservative strategy: when in doubt, always judge the reasoning insufficient and bring that candidate back into the verification flow.
- After the review is complete, the main output should output only the terminator {ot("!!!COMPLETE!!!")}, without mixing in other content. The matter summary awaits a subsequent inquiry.
    """.strip()


def get_review_summary_prompt() -> str:
    """Get the summary prompt of the review Agent"""
    return """
For this round's "review conclusion" structured result, write it only within the markers below, output in the form of a JSON array of objects.
You need to review whether the reasons the clustering Agent used to judge something invalid are sufficient and whether it truly considered all possible paths.

Example 1: Reasoning sufficient (is_reason_sufficient: true, single gid)
<REPORT>
[
  {
    "gid": 1,
    "is_reason_sufficient": true,
    "review_notes": "The clustering Agent has checked all call paths and confirmed that every caller has input validation; the reasoning is sufficient"
  }
]
</REPORT>

Example 2: Reasoning sufficient (is_reason_sufficient: true, multiple gids merged)
<REPORT>
[
  {
    "gids": [1, 2, 3],
    "is_reason_sufficient": true,
    "review_notes": "The clustering Agent has checked all call paths and confirmed that every caller has input validation; the reasoning is sufficient"
  }
]
</REPORT>

Example 3: Reasoning insufficient (is_reason_sufficient: false)
<REPORT>
[
  {
    "gid": 1,
    "is_reason_sufficient": false,
    "review_notes": "The clustering Agent omitted the call path of function X; that path may be unvalidated, so the reasoning is insufficient and re-verification is needed"
  }
]
</REPORT>

Requirements:
- Output the JSON array only between <REPORT> and </REPORT>; do not mix in any other text.
- Array elements are objects containing the following fields:
  - gid: integer (globally unique; corresponds to the gid of the invalid cluster; used for a single warning)
  - gids: integer array (globally unique; corresponds to the gids of the invalid cluster; used when merging multiple warnings)
  - is_reason_sufficient: boolean (true/false), indicating whether the invalid reasoning is sufficient
  - review_notes: string (review explanation, explaining why it is sufficient or insufficient)
- **Merge optimization**: If the review results (is_reason_sufficient) and review explanations (review_notes) of multiple warnings (gid) are exactly the same, you may merge them using a gids array to reduce duplication. Use gid for a single warning and gids for merging multiple warnings. gid and gids cannot appear at the same time.
- You must review all input gids and must not omit any.
- If the reasoning is insufficient (is_reason_sufficient: false), bring that candidate back into the verification flow; if sufficient (true), confirm it as invalid.
    """.strip()


def get_cluster_system_prompt() -> str:
    """Get the system prompt of the clustering Agent"""
    return """
# Single-Agent clustering constraints
- Your main task is to cluster the heuristic candidates within the same file, grouping issues that can be verified together into one class.
- **Clustering principles**:
  - Group issues that can be verified together into one class; the verification conditions do not need to be exactly the same.
  - If multiple candidates can be confirmed through the same verification process, they may be grouped into one class even if their verification conditions differ slightly.
  - Example: multiple pointer-dereference issues can be grouped into one class (verifying "the pointer is non-null before dereference"), even if different pointers are involved.
  - Example: multiple buffer-operation issues can be grouped into one class (verifying "the copy length does not exceed the target buffer capacity"), even if different buffers are involved.
- Verification condition: the key precondition that must hold/be verified in order to determine whether a vulnerability exists. Examples: "pointer p is non-null before dereference", "the copy length does not exceed the target buffer capacity", etc.
- **Completeness requirement**: Every gid must appear in some class and must not be omitted. All input gids must be classified.
- Tools first: if you need to check the context, you may use read_code to read nearby code; do not traverse excessively.
- Write operations are forbidden; only read-only analysis is allowed.
- **Important: conservative strategy for invalid judgments**:
  - When judging a candidate invalid, you must consider all possible paths, call chains, and edge cases.
  - You must consider: all kinds of callers, all kinds of input sources, all kinds of execution paths, and all kinds of boundary conditions.
  - As long as there is any possibility (even a very small one) that the vulnerability can be triggered, it must not be marked invalid (is_invalid: false).
  - Only when it is completely certain, with no possibility whatsoever and all paths verified as safe, may it be marked invalid (is_invalid: true).
  - Conservative principle: when in doubt, always mark false (enter the subsequent verification phase), letting the analysis Agent and verification Agent check in depth.
  - Do not judge something invalid just because you see local protection; you must consider whether other paths bypass that protection.
  - Do not judge something invalid just because you see that a certain caller performs validation; you must consider whether other callers perform no validation.
- **Memory usage**:
  - During clustering, make good use of the memory tool (action=retrieve) to retrieve existing memories, especially those related to the current file or function.
  - If necessary, use the memory tool (action=save) to save the key points of the functions or code snippets seen during clustering, using the function name or file name as the tag.
  - Examples of memory content: a certain function's pointer has been null-checked, a certain function already has input validation, the context of a certain code snippet, etc.
  - Such memories can help the subsequent analysis Agent and verification Agent work more efficiently.
    """.strip()


def get_cluster_summary_prompt() -> str:
    """Get the summary prompt of the clustering Agent"""
    return """
Output the JSON array only between <CLUSTERS> and </CLUSTERS>:
- Each element contains (all fields are required):
  - verification: string (description of the verification condition of this cluster, concise and clear, directly usable for subsequent Agent verification)
  - gids: integer array (the globally unique numbers of the candidates; each element of the input JSON contains a gid, which can be filled in directly)
  - is_invalid: boolean (required, true or false). If true, it means all candidates in this cluster are confirmed invalid/false positives and do not enter subsequent verification; if false, it means they need to enter subsequent verification.
  - invalid_reason: string (required when is_invalid is true, may be omitted when false). It must explain in detail why each candidate is invalid, including:
    * All call paths and callers checked
    * The confirmed protective measures and validation logic
    * Why these protections are effective on all paths
    * Why there is absolutely no triggerable path
    * It must be detailed enough so that the review Agent can verify your judgment
- Requirements:
  - Strict restriction: output the JSON array only between <CLUSTERS> and </CLUSTERS>; output no text in any other location
  - **Completeness requirement (most important)**: All gids in the input JSON must be classified and none may be omitted. Every gid must appear in the gids array of some cluster. This is mandatory and must be strictly followed.
  - **Clustering principles**: Group issues that can be verified together into one class; the verification conditions do not need to be exactly the same. If multiple candidates can be confirmed through the same verification process, they may be grouped into one class even if their verification conditions differ slightly.
  - **Required field**: Every cluster element must contain the is_invalid field, whose value must be true or false and cannot be omitted.
  - **Required field**: When is_invalid is true, the invalid_reason field must be provided, and the reasoning must be sufficiently detailed.
  - No explanation or long text is needed; just give an executable short phrase for the verification condition
  - If clustering is not possible, treat each candidate as its own class, with verification being the minimal confirmation condition for that candidate
  - **Conservative judgment principle for is_invalid**:
    - You must consider all kinds of paths, call chains, input sources, and edge cases.
    - As long as there is any possibility (even a very small one) that the vulnerability can be triggered, you must set is_invalid: false.
    - Only when it is completely certain, with no possibility whatsoever and all paths verified as safe, may you set is_invalid: true.
    - Conservative strategy: when in doubt, always set false, letting the subsequent analysis Agent and verification Agent check in depth.
    - Do not set true just because you see local protection; you must consider whether other paths bypass the protection.
    - Do not set true just because a certain caller performs validation; you must consider whether other callers perform no validation.
    - If you set true, you must explain in detail in invalid_reason all the paths checked and the reasoning.
<CLUSTERS>
[
  {
    "verification": "",
    "gids": [],
    "is_invalid": false
  }
]
</CLUSTERS>
    """.strip()
