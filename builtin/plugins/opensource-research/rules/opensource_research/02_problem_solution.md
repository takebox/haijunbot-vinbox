# Problem and Solution Research

## Research Goals

Deeply understand the core problem an open-source project aims to solve, the technical challenges, and the adopted solution, and grasp the essence of the problem and the path to solving it.

## Research Steps You Must Perform

### Step 1: Identify the Core Problem

**Content that must be searched and analyzed:**

- What is the core problem the project aims to solve
- The background and causes of this problem
- The severity and scope of the problem
- Why this problem is worth solving

**Keywords to search:**

- "[project name] problem statement"
- "[project name] solves what problem"
- "[project name] motivation"
- "[project name] pain points"

**Information sources:**

- The "Motivation" or "Why" section of the official documentation
- The project's design documents or RFCs
- The founder's technical blog or talks
  -search_web to search for the problem the project solves

### Step 2: Analyze the Nature of the Problem and Technical Challenges

**Must be analyzed in depth:**

- What is the root and essence of the problem
- Where the technical difficulties and challenges lie
- The limitations of existing solutions
- Why existing approaches cannot solve it well

**Keywords to search:**

- "[project name] technical challenges"
- "[project name] why existing solutions fail"
- "[project name] limitations of alternatives"
- "[project name] difficulties"

**Information sources:**

- Technical comparison documents
- Problem discussions in Issues
- Analysis articles on technical blogs
- Academic papers (if applicable)

### Step 3: Research the Solution

**Content that must be analyzed:**

- The core solution adopted by the project
- The design philosophy of the solution
- The innovative aspects of the solution
- How the solution addresses the previous challenges

**Key research questions:**

- What is the core idea of this approach
- How the approach solves the problem
- Where the approach's uniqueness lies
- What the theoretical basis of the approach is

**Information sources:**

- The "Architecture" or "Design" section of the official documentation
- Technical white papers or design documents
- Core code comments and documentation
- read_webpage to read technical documentation

### Step 4: Analyze the Technical Path

**Technical path that must be researched:**

- The technical architecture of the implementation
- The rationale for key technology choices
- The trade-offs and decisions in the implementation
- The evolution process of the technical path

**Keywords to search:**

- "[project name] design decisions"
- "[project name] architecture choices"
- "[project name] trade-offs"
- "[project name] technical approach"

**Information sources:**

- Architecture design documents
- RFC (Request for Comments) discussions
- In-depth analysis on technical blogs
- The design document directory of the code repository

### Step 5: Verify the Effectiveness of the Solution

**Verification evidence that must be sought:**

- Whether the approach truly solves the problem
- What real cases and success stories exist
- Performance metrics and data support
- User feedback and reviews

**Keywords to search:**

- "[project name] benchmarks"
- "[project name] case studies"
- "[project name] success stories"
- "[project name] performance metrics"

**Information sources:**

- Official benchmark results
- User case documents
- Third-party review articles
- Community discussions and feedback

## Research Output Requirements

### Document Structure

**Document that must be produced:** `02_problem_solution.md`

**The document must contain the following sections:**

1. Core problem analysis
2. Technical challenge analysis
3. Solution overview
4. Technical path analysis
5. Solution effectiveness verification
6. Reference list

### Content Quality Requirements

- **Must**: analyze using a problem-solution comparison approach
- **Must**: deeply understand the essence of the problem, not just surface descriptions
- **Must**: analyze the rationale and trade-offs of technology choices
- **Must**: provide evidence verifying the solution's effectiveness
- **Must**: all analysis has source citations
- **Forbidden**: only describing features without analyzing the problem solved
- **Forbidden**: speaking in generalities without technical depth

## Research Depth Check

After completing this stage of research, you must confirm:

- [ ] You can clearly explain the core problem the project solves
- [ ] You understand the technical challenges and difficulties of the problem
- [ ] You grasp the core idea of the project's solution
- [ ] You understand the reasons and trade-offs of technology choices
- [ ] You can analyze the effectiveness of the solution
- [ ] All analysis has sufficient basis

## Analysis Framework

### Problem Analysis Framework

**Questions that must be answered:**

- **What**: What exactly is the problem?
- **Why**: Why is this problem important?
- **Who**: Who encounters this problem?
- **When**: In what scenarios does it occur?
- **Impact**: The severity and impact of the problem

### Solution Analysis Framework

**Questions that must be answered:**

- **How**: How to solve the problem?
- **Why this way**: Why adopt this approach?
- **Alternatives**: What alternative approaches exist?
- **Trade-offs**: What trade-offs were made?
- **Innovation**: Where are the innovations?

## Common Mistakes

**❌ Wrong approaches:**

- Listing only feature characteristics without analyzing the problem solved
- Only describing what the approach is without analyzing why it was designed this way
- Lacking technical depth and staying at surface descriptions
- Not verifying the effectiveness of the solution

**✅ Correct approaches:**

- Dig deep into the essence and root of the problem
- Analyze the rationale and trade-offs of technical decisions
- Seek evidence verifying the solution's effectiveness
- Understand the background and context of the problem

## Practical Tips

**In-depth research strategy:**

1. Start by understanding the original motivation from the founder's first article or talk
2. Look at the project's first commit to understand the initial implementation ideas
3. Read the design documents and RFC discussions to understand the thought process
4. Compare the differences before and after the approach was implemented to appreciate the improvement
5. Look for concrete performance test data and user cases
