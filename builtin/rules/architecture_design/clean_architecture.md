---
name: clean_architecture
description: Triggered when there is a need to design or evaluate clean architecture. Triggered whenever the user mentions "clean architecture", "layered architecture", "dependency rule", "business logic separation", "framework decoupling", or "testable architecture". Not triggered: only code conventions without involving architecture design; SOLID principles (use the solid rule); only refactoring without involving architecture evaluation.
---

# Clean Architecture Rule

## Core Principles You Must Follow

### 1. The Dependency Rule (highest priority)

**Execution requirements:**

- **Must**: source code dependencies may only point inward, never outward
- **Must**: the inner layers know nothing about the outer layers
- **Must**: outer layers depend on inner layers through interfaces
- **Forbidden**: inner layers referencing classes, functions, or modules of the outer layers

**Dependency direction:**

```text
Frameworks & Drivers (outermost layer)

  ↑
Interface Adapters
         ↑
   Use Cases
         ↑
   Entities (innermost layer)
```

### 2. The Separation of Concerns Principle

**Execution requirements:**

- **Must**: business logic is completely separated from external details
- **Must**: core business rules do not depend on external details such as frameworks, databases, or UI
- **Must**: external details (database, Web, UI) are plugged in as plugins
- **Forbidden**: mixing framework, database, or UI related code into business logic

**Concern classification:**

- **Entities (entities)**: enterprise business rules
- **Use Cases (use cases)**: application-specific business rules
- **Interface Adapters (interface adapters)**: data format conversion
- **Frameworks & Drivers (frameworks & drivers)**: external tools and frameworks

### 3. The Testability Principle

**Execution requirements:**

- **Must**: core business logic can be tested without depending on external frameworks
- **Must**: Use Cases can be tested without a database or a Web framework
- **Must**: use dependency injection to facilitate testing
- **Forbidden**: tests requiring starting a complete external system (such as a database or a Web server)

## The Architecture Layers You Must Understand

### 1. The Entities Layer (entity layer)

**Responsibilities:**

- Encapsulate enterprise business rules
- As the innermost layer, it depends on no outer layer
- Can be reused across multiple applications

**Requirements:**

- **Must**: depend on no framework
- **Must**: depend on no database, UI, Web, etc.
- **Must**: be independently testable

### 2. The Use Cases Layer (use case layer)

**Responsibilities:**

- Encapsulate application-specific business rules
- Orchestrate Entities to accomplish business goals
- Drive Entities to work

**Requirements:**

- **Must**: depend on no framework, database, or UI
- **Must**: depend only on the Entities layer
- **Must**: define interfaces for the outer layer to implement

### 3. The Interface Adapters Layer (interface adapter layer)

**Responsibilities:**

- Data format conversion
- Convert the data formats of Use Cases into the formats required by frameworks or databases
- Convert external inputs into the formats required by Use Cases

**Requirements:**

- **Must**: depend on no framework details
- **Must**: depend only on the Use Cases and Entities layers
- **Must**: interact with the outer layer through interfaces

### 4. The Frameworks & Drivers Layer (framework and driver layer)

**Responsibilities:**

- Contains external tools such as frameworks, databases, Web frameworks, and UI
- As the outermost layer, it contains no business logic
- Provides concrete implementations

**Requirements:**

- **Must**: contain no business rules
- **Must**: depend on all inner layers
- **Must**: be easily replaceable (through interfaces)

## Practical Conventions (must be followed)

### Dependency management

- **Must**: define interfaces in the inner layers, put implementations in the outer layers
- **Must**: use dependency injection to inject outer layer implementations into the inner layers
- **Forbidden**: inner layers directly referencing concrete classes of the outer layers
- **Forbidden**: directly calling framework APIs in business logic

### Business logic isolation

- **Must**: business rule code appears only in the Entities and Use Cases layers
- **Forbidden**: writing business logic in the Interface Adapters or Frameworks layers
- **Forbidden**: mixing database operations, HTTP requests, etc. into business logic

### Data access separation

- **Must**: Entities depend on no database implementation
- **Must**: access data through an interface (Repository)
- **Must**: put the database implementation in the Frameworks layer

## Code Examples

### ❌ A practice to avoid (violates clean architecture)

```python
# business logic directly depends on the database and frameworks

class OrderService:
    def __init__(self):
        # violation: an inner layer directly depends on an outer-layer database framework
        self.db = DatabaseConnection()  # depends on a database framework
        self.http_client = HttpClient()   # depends on an HTTP framework

    def process_order(self, order_id: int) -> dict:
        # violation: database operations mixed into business logic
        order_data = self.db.query(f"SELECT * FROM orders WHERE id = {order_id}")

        # violation: HTTP requests mixed into business logic
        user_data = self.http_client.get(f"/api/users/{order_data['user_id']}")

        # business rules
        if order_data['amount'] > 1000 and user_data['is_vip']:
            discount = 0.1
        else:
            discount = 0.0

        # violation: directly returning data in database format
        return {
            'order_id': order_id,
            'total': order_data['amount'] * (1 - discount),
            'raw_data': order_data  # exposes the internal data structure
        }
```

### ✅ Recommended practice (conforms to clean architecture)

```python
# Entities layer: business rules

class Order:
    def __init__(self, order_id: int, amount: float, user_id: int):
        self.order_id = order_id
        self.amount = amount
        self.user_id = user_id

    def calculate_discount(self, user_is_vip: bool) -> float:
        """Calculate the discount (business rule)"""
        if self.amount > 1000 and user_is_vip:
            return 0.1
        return 0.0


# Use Cases layer: applying the business rules

class ProcessOrderUseCase:
    def __init__(self, order_repository: 'OrderRepository', user_service: 'UserService'):
        # dependency injection: depends on the outer layer through interfaces
        self.order_repository = order_repository
        self.user_service = user_service

    def execute(self, order_id: int) -> ProcessOrderResult:
        """Process the order (application logic)"""
        order = self.order_repository.get_by_id(order_id)
        user = self.user_service.get_user(order.user_id)

        discount = order.calculate_discount(user.is_vip)
        total = order.amount * (1 - discount)

        return ProcessOrderResult(
            order_id=order_id,
            total=total,
            discount=discount
        )


# data class (DTO)

class ProcessOrderResult:
    def __init__(self, order_id: int, total: float, discount: float):
        self.order_id = order_id
        self.total = total
        self.discount = discount


# interface definitions (in the inner layer)

from abc import ABC, abstractmethod

class OrderRepository(ABC):
    @abstractmethod
    def get_by_id(self, order_id: int) -> Order:
        pass

    @abstractmethod
    def save(self, order: Order) -> None:
        pass


class UserService(ABC):
    @abstractmethod
    def get_user(self, user_id: int) -> 'User':
        pass


class User:
    def __init__(self, user_id: int, is_vip: bool):
        self.user_id = user_id
        self.is_vip = is_vip


# Frameworks layer: concrete implementations (outer layer)

class DatabaseOrderRepository(OrderRepository):
    def __init__(self, db_connection: 'DatabaseConnection'):
        self.db = db_connection  # the outer layer depends on the framework

    def get_by_id(self, order_id: int) -> Order:
        # database operations are encapsulated in the outer layer
        data = self.db.query("SELECT * FROM orders WHERE id = %s", order_id)
        return Order(data['id'], data['amount'], data['user_id'])

    def save(self, order: Order) -> None:
        self.db.execute(
            "INSERT INTO orders VALUES (%s, %s, %s)",
            order.order_id, order.amount, order.user_id
        )


class HttpUserService(UserService):
    def __init__(self, http_client: 'HttpClient'):
        self.http = http_client  # the outer layer depends on the framework

    def get_user(self, user_id: int) -> User:
        # HTTP requests are encapsulated in the outer layer
        data = self.http.get(f"/api/users/{user_id}")
        return User(data['id'], data['is_vip'])
```

## Clean Architecture Checklist

Before writing code, be sure to confirm:

### Dependency direction check

- [ ] Does the source code dependency direction point inward
- [ ] Does the inner layer have no references to concrete classes of the outer layers
- [ ] Are interface definitions in the inner layers
- [ ] Are concrete implementations in the outer layers

### Business logic check

- [ ] Do business rules appear only in the Entities and Use Cases layers
- [ ] Is the business logic independent of frameworks, databases, and UI
- [ ] Do Entities depend on no external details
- [ ] Do Use Cases depend only on the Entities layer

### Data access check

- [ ] Are database operations encapsulated in the outermost layer
- [ ] Is data accessed through an interface (Repository)
- [ ] Is data format conversion in the Interface Adapters layer
- [ ] Is the internal data structure exposed

### Testability check

- [ ] Can the core business logic be tested without starting external systems
- [ ] Is dependency injection used to facilitate testing
- [ ] Can outer layer dependencies be easily mocked
- [ ] Do the tests require external facilities such as a database or a Web server

### Architecture layering check

- [ ] Does the Entities layer contain only enterprise business rules
- [ ] Does the Use Cases layer orchestrate Entities to accomplish business goals
- [ ] Does the Interface Adapters layer only do data format conversion
- [ ] Does the Frameworks layer contain no business logic

### Code organization check

- [ ] Is each layer's code placed in a different directory or package
- [ ] Are there clear layer boundaries
- [ ] Are there explicit interface definitions
- [ ] Is it easy to understand and maintain
