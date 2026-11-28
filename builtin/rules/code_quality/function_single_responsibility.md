---
name: function_single_responsibility
description: Triggered when functions violating the single responsibility principle need to be identified and refactored. Triggered whenever the user mentions "single responsibility", "function splitting", "refactor functions", "overly long functions", "complex functions", "code smells". Not triggered: code review (use the code_review rules); performance optimization; security review.
---

# Function Single Responsibility Refactoring

## Rule Introduction

This rule defines the requirements and refactoring methods for the function single responsibility principle. The single responsibility principle requires that a function does only one thing and does it well. Functions that violate the single responsibility principle usually exhibit: complex logic, difficulty understanding, difficulty testing, and difficulty reusing.

## Principles You Must Follow

### 1. Unique Function Responsibility

**Requirement Description:**

- **Must**: Each function completes only one clear business logic or functionality
- **Must**: The function name should accurately describe the function's single responsibility
- **Forbidden**: Mixing multiple logic levels in the same function (such as: data validation, business processing, data persistence)

**Judgment Criteria:**

If you cannot clearly describe "what this function does" in one sentence, it may violate the single responsibility principle.

### 2. Function Length Control

**Requirement Description:**

- **Must**: Function length (including comments and blank lines) does not exceed 50 lines
- **Must**: The function's complexity (cyclomatic complexity) does not exceed 10
- **Forbidden**: Nesting structures exceeding 3 levels

### 3. Parameter Count Limit

**Requirement Description:**

- **Must**: Function parameters do not exceed 5
- **Must**: When parameters exceed 3, consider using an object wrapper or data class
- **Forbidden**: Using variable argument lists to conceal excessive parameters

## Mandatory Operations

### Operation 1: Identify Functions Violating Single Responsibility

**Execution Steps:**

1. Review the function name and judge whether it accurately describes the function behavior
2. Check the function length; if it exceeds 50 lines, mark it for refactoring
3. Analyze the function logic and identify whether multiple responsibilities exist
4. Check the parameter count; if it exceeds 5, mark it for refactoring

**Common Anti-patterns:**

- Function names containing conjunctions such as "and", "or", "andThen"
- Functions containing too many if/else branches handling many different situations
- Functions simultaneously performing data validation, business logic, database operations, and logging

### Operation 2: Refactor Functions

**Execution Steps:**

1. **Extract independent logic**: Extract independent logic blocks in the function into separate functions
2. **Reduce complexity**: Use early returns to reduce nesting levels
3. **Encapsulate parameter objects**: Use data classes or dictionaries to encapsulate related parameters
4. **Naming optimization**: Ensure each function name accurately describes its single responsibility

**Notes:**

- Keep refactoring steps small enough, changing only one part at a time
- Maintain the same external behavior before and after refactoring
- Perform unit test verification on the refactored code

### Operation 3: Verify Refactoring Results

**Execution Steps:**

1. Confirm the length of each new function does not exceed 50 lines
2. Confirm each function's single responsibility can be clearly described
3. Confirm all unit tests pass
4. Confirm code readability has significantly improved

### Example

#### Wrong Example: Violating Single Responsibility

```python
def process_user_order(user_id, order_data, product_id, quantity, payment_info, shipping_info):
    """Process user order (violates single responsibility: includes validation, business processing, persistence, notification)"""
    # Step 1: Validate user (responsibility 1)
    if not validate_user(user_id):
        return {"error": "Invalid user"}

    # Step 2: Validate product (responsibility 2)
    if not validate_product(product_id, quantity):
        return {"error": "Invalid product"}

    # Step 3: Calculate price (responsibility 3)
    total_price = calculate_price(product_id, quantity)

    # Step 4: Process payment (responsibility 4)
    payment_result = process_payment(payment_info, total_price)
    if not payment_result["success"]:
        return {"error": "Payment failed"}

    # Step 5: Save order (responsibility 5)
    order_id = save_order_to_db(user_id, product_id, quantity, total_price)

    # Step 6: Send notification (responsibility 6)
    send_confirmation_email(user_id, order_id)

    return {"success": True, "order_id": order_id}
```

#### Correct Example: Following Single Responsibility

```python
def process_user_order(user_id: str, order_data: dict) -> dict:
    """Main flow for processing a user order (coordinates the various single-responsibility functions)"""
    try:
        validate_user(user_id)
        validate_order_data(order_data)
        total_price = calculate_order_total(order_data)
        payment_result = process_payment(order_data["payment_info"], total_price)
        order_id = save_order(user_id, order_data, total_price)
        send_order_notification(user_id, order_id)
        return {"success": True, "order_id": order_id}
    except ValidationError as e:
        return {"error": str(e)}
    except PaymentError as e:
        return {"error": str(e)}

def validate_user(user_id: str) -> None:
    """Validate whether the user is valid"""
    if not user_exists(user_id):
        raise ValidationError("Invalid user")

def validate_order_data(order_data: dict) -> None:
    """Validate order data"""
    if "product_id" not in order_data or "quantity" not in order_data:
        raise ValidationError("Invalid order data")

def calculate_order_total(order_data: dict) -> float:
    """Calculate the total order price"""
    product_price = get_product_price(order_data["product_id"])
    return product_price * order_data["quantity"]

def process_payment(payment_info: dict, amount: float) -> dict:
    """Process payment"""
    payment_service = PaymentService()
    return payment_service.charge(payment_info, amount)

def save_order(user_id: str, order_data: dict, total_price: float) -> str:
    """Save the order to the database"""
    order = Order(
        user_id=user_id,
        product_id=order_data["product_id"],
        quantity=order_data["quantity"],
        total_price=total_price
    )
    order.save()
    return str(order.id)

def send_order_notification(user_id: str, order_id: str) -> None:
    """Send order notification"""
    user_email = get_user_email(user_id)
    EmailService().send_order_confirmation(user_email, order_id)
```

## Checklist

After completing the function single responsibility refactoring, please make sure to confirm:

- [ ] Every function has a clear and explicit single responsibility
- [ ] Each function's functionality can be described in one sentence
- [ ] All functions are no more than 50 lines long
- [ ] All functions have no more than 5 parameters
- [ ] No nesting structures exceeding 3 levels
- [ ] Function names accurately describe their responsibilities
- [ ] Unit tests have been written or updated
- [ ] All unit tests pass
- [ ] Code readability has significantly improved

## Related Resources

- Related rules: `{{ rule_file_dir }}/code_quality/code_review.md`
- Reference standard: Clean Code chapter on functions
