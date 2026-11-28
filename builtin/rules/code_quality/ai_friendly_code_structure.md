---
name: ai_friendly_code_structure
description: Triggered when there is a need to write or refactor code to improve AI comprehensibility. Triggered whenever the user mentions "AI-friendly code", "code structure optimization", "easy for AI to understand", or "code readability". Not triggered: pure feature implementation that does not involve structure optimization; performance optimization (use the performance rule); security review.
---

# AI-Friendly Code Structure Specification

## Rule Introduction

This specification defines the structural requirements for writing AI-friendly code, aiming to make code easy for an AI Agent to understand, analyze, and maintain. Following this specification can significantly improve the efficiency and accuracy of AI-assisted programming.

**Important prerequisite**: before any code structure modification or optimization, **you should ensure there is sufficient test case coverage**. Test coverage is the safety guarantee for code refactoring; modifying code without test coverage is high risk.

## Principles You Must Follow

### 1. File Size Limit

**Requirement description:**

- **Must**: a single source code file should not exceed 1000 lines (excluding blank lines and comments)
- **Must**: when a file exceeds 800 lines, splitting should be considered
- **Forbidden**: placing unrelated feature modules in the same file
- **Exception**: if a file's functionality is extremely cohesive (such as a core algorithm or domain model definition), splitting would instead harm readability, so the original file may be retained but an explanatory comment should be added

**Splitting strategy:**

- Split by feature module: different business logic goes into different files
- Split by responsibility: data models, business logic, and interface definitions are stored separately
- Split by reusability: general utility functions are extracted into independent modules

**Example:**

```python
# ✅ Correct: single file responsibility, about 200 lines
# user_service.py - only handles user-related business logic
class UserService:
    def create_user(self, ...): ...
    def get_user(self, ...): ...
    def update_user(self, ...): ...

# ✅ Correct: utility functions in their own file
# utils/validation.py - only contains validation-related functions
def validate_email(...): ...
def validate_phone(...): ...
```

### 2. Function Length Limit

**Requirement description:**

- **Must**: a single function should not exceed 50 lines (excluding blank lines and comments)
- **Must**: when a function exceeds 40 lines, extracting sub-functions should be considered
- **Forbidden**: conditionals nested more than 3 levels deep within a function

**Splitting strategy:**

- Extract sub-functions: extract independent logic blocks into private methods
- Early return: use guard clauses to reduce nesting
- Strategy pattern: use the strategy pattern for complex conditional branches

**Example:**

```python
# ✅ Correct: single function responsibility, about 20 lines
def process_order(order: Order) -> bool:
    """Process the order, return whether it succeeded"""
    if not validate_order(order):
        return False

    if not check_inventory(order.items):
        return False

    total = calculate_total(order)
    return charge_payment(order.user, total)

# ❌ Wrong: function too long, over 80 lines
def process_order(order):
    # validation logic... (20 lines)
    # inventory check... (20 lines)
    # price calculation... (20 lines)
    # payment processing... (20 lines)
    # logging... (10 lines)
    pass
```

### 3. Single Responsibility Principle

**Requirement description:**

- **Must**: each class/function is responsible for only one clear responsibility
- **Must**: class names and function names accurately reflect their sole responsibility
- **Forbidden**: mixing business logic into utility classes

**Example:**

```python
# ✅ Correct: separation of responsibilities
class UserAuthenticator:
    """Only responsible for user authentication"""
    def authenticate(self, ...): ...

class UserProfileManager:
    """Only responsible for user profile management"""
    def update_profile(self, ...): ...

# ❌ Wrong: mixed responsibilities
class UserManager:
    # manages authentication, profiles, and permissions...
    def login(self, ...): ...
    def update_profile(self, ...): ...
    def assign_role(self, ...): ...
```

### 4. Clear Naming Convention

**Requirement description:**

- **Must**: use meaningful names and avoid abbreviations (except common abbreviations)
- **Must**: variable names reflect the data type and purpose
- **Must**: function names reflect the operation and behavior (verb + noun)
- **Forbidden**: using vague names such as `a`, `b`, `temp`, `data`

**Example:**

```python
# ✅ Correct: clear naming
def calculate_monthly_revenue(orders: List[Order]) -> Decimal: ...
def find_active_users_by_department(dept_id: int) -> List[User]: ...
user_creation_timestamp: datetime
max_retry_count: int = 3

# ❌ Wrong: vague naming
def calc(data): ...
def find(id): ...
tmp = ...
info = ...
```

### 5. Appropriate Comments

**Requirement description:**

- **Must**: write docstrings for public APIs
- **Must**: write implementation-approach comments for complex algorithms
- **Must**: write "why it is done this way" comments for non-intuitive code
- **Forbidden**: comments that repeat the code itself ("what" rather than "why")

**Example:**

```python
# ✅ Correct: the comment explains the reason
def retry_request(url: str, max_retries: int = 3) -> Response:
    """
    Send an HTTP request, automatically retrying on failure.

    Use an exponential backoff strategy, because immediate retries may increase the server load.
    """
    for attempt in range(max_retries):
        # Exponential backoff: 1s, 2s, 4s...
        # Avoid a request storm and give the server time to recover
        wait_time = 2 ** attempt
        time.sleep(wait_time)

        try:
            return http.get(url)
        except ConnectionError:
            if attempt == max_retries - 1:
                raise

# ❌ Wrong: the comment repeats the code
i += 1  # increment i by 1
return result  # return the result
```

### 6. Flat Nesting Structure

**Requirement description:**

- **Must**: code nesting levels should not exceed 3
- **Must**: use guard clauses (early return) to reduce nesting
- **Forbidden**: deeply nested if-else or try-except

**Example:**

```python
# ✅ Correct: flat structure (maximum nesting 2 levels)
def process_data(data: Optional[Dict]) -> Result:
    if data is None:
        return Error("Data is None")

    if "items" not in data:
        return Error("Missing items")

    for item in data["items"]:
        if not is_valid(item):
            continue
        process_item(item)

    return Success()

# ❌ Wrong: deep nesting (5 levels)
def process_data(data):
    if data is not None:
        if "items" in data:
            for item in data["items"]:
                if is_valid(item):
                    try:
                        process_item(item)
                    except Exception:
                        pass
```

### 7. Orthogonal Design

**Requirement description:**

- **Must**: keep low coupling between modules
- **Must**: each module has clear input/output boundaries
- **Forbidden**: circular dependencies and implicit global state

**Example:**

```python
# ✅ Correct: orthogonal design
# Module A: only depends on the interface, not the concrete implementation
class PaymentProcessor:
    def __init__(self, gateway: PaymentGateway):  # depends on an abstraction
        self.gateway = gateway

    def process(self, amount: Decimal) -> bool:
        return self.gateway.charge(amount)

# ❌ Wrong: severe coupling
class PaymentProcessor:
    def process(self, amount):
        # directly depends on a concrete implementation
        from alipay_sdk import Alipay
        alipay = Alipay(...)
        return alipay.charge(amount)
```

## Operations You Must Perform

### Operation 0: Test Coverage Check (mandatory)

**Execution steps:**

1. Before any code structure modification, **first check the test coverage**
2. Run the existing tests and confirm a 100% test pass rate
3. Check the test coverage; the core business logic coverage should be ≥ 80%
4. If test coverage is insufficient, **code structure modification is forbidden**; test cases should be added first
5. Record the test coverage as the baseline for refactoring safety

**Example:**

```bash
# Run the tests and check coverage
pytest tests/ --cov=src/ --cov-report=term-missing

# Confirm the tests pass
# Confirm the core module coverage is ≥ 80%
```

### Operation 1: Check During Code Review

**Execution steps:**

1. Count the file lines (excluding blank lines and comments) and confirm ≤ 500 lines
2. Count the function lines (excluding blank lines and comments) and confirm ≤ 50 lines
3. Check the nesting levels and confirm ≤ 3 levels
4. Review whether the naming is clear and meaningful
5. Confirm that comments explain "why" rather than "what"

### Operation 2: Refactor Overly Long Files

**Execution steps:**

1. Identify the different responsibility modules in the file
2. Extract each responsibility module into an independent file
3. Keep the original function signatures in the new files
4. Import and forward the calls in the original file
5. Run the tests to ensure the behavior is unchanged

### Operation 3: Refactor Overly Long Functions

**Execution steps:**

1. Identify the independent logic blocks in the function
2. Extract each logic block into a private method
3. Choose clear names for the new methods
4. Call the new methods in the original function
5. Run the tests to ensure the behavior is unchanged

## Checklist

After writing or reviewing code, be sure to confirm:

- [ ] **The test coverage check has passed** (100% test pass rate, core business logic coverage ≥ 80%)
- [ ] All source files do not exceed 500 lines (excluding blank lines and comments)
- [ ] All functions do not exceed 50 lines (excluding blank lines and comments)
- [ ] All classes/functions bear only a single responsibility
- [ ] All naming is clear and meaningful
- [ ] Key code has comments explaining "why"
- [ ] The code nesting levels do not exceed 3
- [ ] There are no circular dependencies between modules

## AI-Friendliness Measurement Dimensions

This specification revolves around **7 key dimensions** to ensure the code structure is friendly to an AI Agent:

### Dimension 1: Context Window Adaptability

**Focus**: whether the code volume and retrieval paths adapt to AI context limits

**Core indicators**:

- Average tokens per module < 150K
- Tokens per file < 10K (data layer ≤ 15K)
- Average tokens per function/method < 500 (complex functions ≤ 800)
- Dependency context overhead: within a module < 50K, cross-module < 30K and ≤ 3 external modules
- Key path retrieval depth: number of files ≤ 5, number of levels ≤ 4
- Interface definition token proportion: data layer 30–50%, business layer 10–20%, interface layer 20–30%
- Effective semantic comment density ≥ 60

### Dimension 2: Semantic Comprehensibility

**Focus**: naming consistent with the implementation, comments eliminating ambiguity, implicit behavior made explicit

**Core indicators**:

- Domain terminology coverage = 100%
- Naming-implementation consistency score ≥ 85
- Naming ambiguity rate ≤ 5%
- Naming convention consistency = 100%
- Contract-based comment coverage ≥ 95%
- Implicit behavior explicit-ization rate = 100%
- Business rule hardcoding rate ≤ 10%
- Average code cyclomatic complexity ≤ 10

### Dimension 3: Structural Navigability

**Focus**: clear module responsibilities, cohesion, dependencies, directories, and interface boundaries

**Core indicators**:

- Directory structure compliance rate ≥ 95%
- Architecture layering adherence = 100% (no illegal cross-layer calls)
- Cross-module dependency clarity = 100% (explicit dependencies, no cycles)
- Module cohesion coefficient ≥ 2.0
- Module responsibility singularity: external interfaces ≤ 10, subdirectories ≤ 5
- Entry point convergence < 5
- Interface boundary clarity = 100%
- Fan-in/fan-out ratio ≥ 1.0 (public modules exempt)

### Dimension 4: Change Locality

**Focus**: functional cohesion, controllable modification impact, explicit side effects

**Core indicators**:

- Business function call chain depth ≤ 8 levels
- Single-point change impact scope ≤ 5 modules or ≤ 10 files
- Side effect explicit-ization rate = 100%
- Side effect isolation: pure functions ≥ 60%, global modification points ≤ 10/module
- Configuration externalization rate ≥ 90%
- Logic-configuration balance ≤ 10%

### Dimension 5: Test Verifiability

**Focus**: adequate testability design, testable core logic, boundary and exception coverage

**Core indicators**:

- Testability design score ≥ 80
- Core logic test coverage ≥ 80%
- Key path test coverage ≥ 90%
- Interface verification coverage = 100%
- AI-generated code verification coverage = 100%

### Dimension 6: Pattern Consistency

**Focus**: unified architecture patterns, coding style, error handling, and logging conventions

**Core indicators**:

- Coding convention compliance rate ≥ 95%
- Layering/architecture pattern uniformity = 100%
- API semantic level = 100%

### Dimension 7: Documentation Completeness

**Focus**: documentation synchronized with code, no drift, executable examples, traceable changes

**Core indicators**:

- Documentation drift detection pass rate = 100%
- Documentation-code consistency ≥ 90
- API documentation completeness rate = 100%
- Example code executability rate = 100%
- Change traceability ≥ 90%

## AI-Friendliness Scoring Model

### Scoring Formula

```text
Score = 0.8 × Score_rules + 0.2 × Score_AI_stats
```

- `Score_rules`: the weighted score of the **rule-based indicators** across the 7 dimensions
- `Score_AI_stats`: the sample average score of the **AI Agent statistical indicators**

### Dimension Weights

| Dimension             | Weight |
| --------------------- | ------ |
| Context window adaptability | 20%  |
| Semantic comprehensibility | 20%  |
| Structural navigability | 20%  |
| Change locality       | 15%  |
| Test verifiability    | 10%  |
| Pattern consistency   | 10%  |
| Documentation completeness | 5%   |

### Grade Standards

| Grade       | Score range | Meaning                       |
| ----------- | ----------- | ----------------------------- |
| **Grade S** | 90–100      | AI native-friendly, fully automated development possible |
| **Grade A** | 75–89       | AI-friendly and excellent, suitable for AI-assisted development |
| **Grade B** | 60–74       | Basically usable, needs moderate optimization |
| **Grade C** | 40–59       | Difficult for AI development, needs refactoring |
| **Grade D** | 0–39        | Not suitable for AI development |

### CI Gate Passing Conditions

1. **No veto items** (AI anti-patterns)
2. Rule score ≥ 80
3. AI statistical score ≥ 75
4. 100% pass on strong gate items
5. AI statistical indicators **confidence ≥ 80%**
   - Confidence 95%: normal gate
   - Confidence 80%: warning only, merging allowed

## AI Anti-Pattern List (Veto Items)

If **any one of the following anti-patterns is present, it must not be rated Grade A or above**:

1. **Deeply nested macro definitions/metaprogramming**: difficult for AI to analyze statically, extremely high comprehension cost
2. **Runtime dynamic proxy without type hints**: AI cannot infer the actual type and behavior
3. **Magic strings/numbers hardcoded without enum mapping**: unclear semantics, AI cannot understand the business meaning
4. **Implicit event publishing without explicit annotation**: hidden side effects, AI cannot trace the data flow
5. **Abuse of global mutable state**: unpredictable state, AI cannot reason about program behavior
6. **Configuration-driven complex flow control**: scattered logic, AI cannot build a complete model

## AI Agent Statistical Indicators

### Measurement Mode Definitions

1. **Rule-based indicators**: computed through **deterministic rules** such as AST, static scanning, Tokenizer, and directory structure; 100% reproducible; strong CI gate

2. **AI Agent statistical indicators**: for **semantic and intent-based indicators**, adopt **random sampling + probability statistics + interval judgment**, not full line-by-line coverage, using the statistical results as the gate basis

3. **Experimental indicators**: used for iterative calibration and retrospective analysis, **not included in the CI gate**

### Global Sampling and Statistics Rules

All AI Agent statistical indicators uniformly follow:

1. **Sampling objects**: functions/methods/interfaces/classes
2. **Sampling ratio**: **5%~10%**, with a **minimum of 3 samples per module**
3. **Scoring method**: continuous scoring from 0~100
4. **Statistical basis**:
   - **Sample average score** = total score / number of samples
   - **Sample pass rate** = number of samples with score ≥ threshold / total number of samples

### Confidence Rules

- Sample size ≥ 5: **confidence 95%**
- Sample size 3~4: **confidence 80%**
- Sample size < 3: **confidence 0%, not included in the gate**

### Interval Judgment Rules

- ≥ target score: **pass**
- target score−5 ~ target score: **warning, does not block**
- < target score−5: **fail**

## Related Resources

- Reference code quality rule: `{{ rule_file_dir }}/code_review.md`
- Reference refactoring process: `{{ rule_file_dir }}/../development_workflow/refactoring.md`
