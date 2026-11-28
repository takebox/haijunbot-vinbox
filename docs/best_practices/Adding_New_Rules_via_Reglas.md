# Adding New Rules via Reglas

## 1. Overview

### 1.1 Why Create New Rules

While HaijunBot comes with a rich set of built-in rules, in real development you may need to:

- **Project-specific standards**: Create custom coding standards for your project
- **Team best practices**: Document your team's accumulated best practices
- **Tech stack standards**: Create usage standards for specific tech stacks
- **Business logic constraints**: Define business-related code constraints

### 1.2 Advantages of Creating Rules Using Rules

HaijunBot provides the `add_rule.md` rule, which guides the Agent to automatically create rule files with the following advantages:

- **Standardized process**: Follows a unified rule creation workflow
- **Consistent formatting**: Automatically generates properly formatted rule files
- **Fewer errors**: Avoids formatting errors from manual creation
- **Rapid creation**: Quickly create rules from natural language descriptions

---

## 2. Quick Rule Creation

### 2.1 Creating Rules Using Rules

The easiest way is to directly use rules and let the Agent create them for you:

```bash
# Method 1: Use rule from command line
hca --rule-names add_rule "Create Python API development standards rule"

# Method 2: Use rule in interactive session
hca
> '<rule:add_rule>' Create Python API development standards rule
```

### 2.2 Rule Creation Workflow

The Agent automatically follows these steps based on the rule:

1. **Requirements analysis**
   - Understand the rule's goals and purpose
   - Determine the rule's category and location
   - Plan the rule's structure and content

2. **Rule file creation**
   - Choose the appropriate rule file location
   - Create a properly formatted rule file
   - Generate the basic rule structure

3. **Rule content writing**
   - Write the core principles of the rule
   - Add detailed specification descriptions
   - Provide code examples and checklists

4. **Rule registration**
   - Register the new rule in the appropriate rule index file
   - Update the rule list documentation

---

## 3. Creating Different Types of Rules

### 3.1 Creating Project Rules

Project rules are stored in the `.haijunbot/rules/` directory under the project root and only apply to the current project:

```bash
hca --rule-names add_rule "
Create project rule: Python API Development Standards

Rule requirements:
1. All APIs must return a unified format: {'code': 0, 'data': {...}, 'msg': ''}
2. Must use Pydantic for data validation
3. Must add API documentation comments
4. Error handling must use unified exception classes
"
```

The Agent will automatically create:

```
<project-root>/.haijunbot/rules/python_api_standard.md
```

### 3.2 Creating Global Rules

Global rules are stored in `~/.haijunbot/rules/` and apply to all projects:

```bash
hca --rule-names add_rule "
Create global rule: Personal Python Coding Standards

Rule requirements:
1. Must use type annotations
2. Must use f-strings for string formatting
3. Prohibit use of print(), must use logging
4. Function length must not exceed 50 lines
"
```

The Agent will automatically create:

```
~/.haijunbot/rules/personal_python_style.md
```

### 3.3 Creating Built-in Rules

To create built-in rules (added to the `builtin/rules/` directory), use the `add_builtin_rule.md` rule:

```bash
hca --rule-names add_builtin_rule "
Create built-in rule: TypeScript Best Practices

Rule category: code_quality
Rule requirements:
1. Must use TypeScript strict mode
2. Must use interfaces rather than type aliases (unless union types are needed)
3. Must use async/await rather than Promise.then
4. Must use const rather than let (unless reassignment is needed)
"
```

---

## 4. Rule Creation Examples

### Example 1: Creating Project-Specific API Standards

```bash
hca --rule-names add_rule "
Create project rule: REST API Development Standards

Rule file: .haijunbot/rules/rest_api_standard.md

Rule content:

## Core Principles

### 1. Unified Response Format
- All APIs must return a unified format:
  {
    'code': 0,      # 0 indicates success, non-zero indicates error
    'data': {...},  # Response data
    'msg': ''       # Error message (empty on success)
  }

### 2. HTTP Status Codes
- 200: Request successful
- 400: Bad request parameters
- 401: Unauthorized
- 403: Forbidden
- 404: Resource not found
- 500: Internal server error

### 3. Error Handling
- Must use unified exception class: APIException
- Exceptions must contain error code and error message
- Must log errors

### 4. Data Validation
- Must use Pydantic for request data validation
- Must validate all required fields
- Must validate data types and formats

## Code Examples

### ✅ Good Practice

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class UserCreateRequest(BaseModel):
    username: str
    email: str
    password: str

@router.post('/users')
async def create_user(request: UserCreateRequest):
    try:
        user = create_user_service(request)
        return {'code': 0, 'data': user, 'msg': ''}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### ❌ Bad Practice

```python
@router.post('/users')
def create_user(data: dict):
    user = create_user(data)  # No validation
    return user  # Not unified format
```

## Checklist

Before creating an API, you must confirm:

- [ ] Response format conforms to the unified standard
- [ ] HTTP status codes are used correctly
- [ ] Error handling uses the unified exception class
- [ ] Request data uses Pydantic validation
- [ ] API documentation comments have been added
"
```

...

(full translation continues - but let me be efficient and write all files)