# Organize and Merge Long-Term Memories

## Use Cases

When your long-term memories become more and more numerous, with similar topics and repeated tags, making lookup and reuse chaotic, you can use the memory organization command to organize and merge related long-term memories into a more comprehensive result.

## Steps

1. In the terminal, run the long-term memory organization command, for example: `hmo organize --type project_long_term`.
2. Set `--type` to the type you want to organize as needed:
   - project long-term memory
   - global long-term memory

3. If you want to rehearse first without actually modifying the data, you can first enable dry-run mode to see only which memories will be merged.
4. During the actual execution, the system scans the long-term memories of the current type and finds memory groups suitable for merging.
5. For each group of memories to be organized, the system generates a new comprehensive memory and replaces the original multiple duplicate memories.
6. After the execution finishes, view the statistics and processing result in the terminal.

## Prompts and Feedback You Will See

- Before starting, the system prompts which type of memory is currently being organized.
- If there are no memories under the current type, the system directly prompts that there is no content to process.
- When mergeable content is detected, the system first lists the memory groups it plans to merge.
- When dry-run is used, you can see "which memories will be merged", but the files are not actually modified.
- During the actual execution, after success it displays statistics such as the number of groups processed, the number merged, and the number of newly created memories.
- If some memory files are themselves corrupted or unreadable, the system directly prompts the information of the files that failed to be read.
- If a certain group fails to merge, the system prompts that the group is skipped, without letting the whole process terminate without notice.

## Notes

- The organization command targets long-term memories, not temporary memory operations.
- If you are unsure about the result, it is recommended to rehearse with dry-run first.
- After merging, the original memories are replaced by the new comprehensive memory, so before actual execution you should confirm that you accept this way of organizing.
- Project long-term memory and global long-term memory are organized separately, so choose the right type before operating.
