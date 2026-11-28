# Automatically Filtering Relevant Methodologies Based on Current Needs

## Use Cases

If you have already prepared many methodologies but do not want to pick them by hand every time, HaijunBot will automatically filter the more relevant methodologies for subsequent use based on the current needs when required.

## Steps

1. First make sure the methodology sources are ready, for example:
   - Default methodology directory
   - Project-level methodology directory
   - `methodology_dirs`
   - `central_methodology_repo`
2. Start the relevant Agent and enter your task requirements.
3. When the system enters the methodology loading flow, it first loads all available methodology titles.
4. Then the system automatically selects the more relevant methodologies based on the current needs and available tools.
5. Observe the methodology loading prompts and subsequent task behavior to confirm whether the filtered methodologies have participated in the current task.

## Prompts and Feedback You Will See

- The system usually first prompts "loading methodology files".
- If the methodologies are loaded successfully, it prompts the total count.
- If no available methodologies are found, the system gives a relevant warning.
- The actual filtering result usually shows up in subsequent task behavior: the system is more likely to reference experience more relevant to the current problem.

## Notes

- This capability depends on you preparing the methodology sources first; when there are no methodology files, the system cannot filter.
- Automatic filtering is a relevance-based selection and does not guarantee it will fully match your subjective expectations every time.
- If you find the filtering result unsatisfactory, first check the methodology title naming, content quality, and whether the methodology sources are actually loaded correctly.
