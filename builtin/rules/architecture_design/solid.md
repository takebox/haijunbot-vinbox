---
name: solid
description: Triggered when there is a need to apply the SOLID design principles. Triggered whenever the user mentions "SOLID", "single responsibility", "open/closed principle", "Liskov substitution", "interface segregation", or "dependency inversion". Not triggered: clean architecture design (use the clean_architecture rule); only code conventions without involving design principles; functional programming that does not involve OOP.
---

# SOLID Design Principles Rule

## Core Principles You Must Follow

### 1. Single Responsibility Principle (SRP)

**Principle definition:**

A class should have only one reason to change, that is, a class should bear only one responsibility.

**Execution requirements:**

- **Must**: each class is responsible for only one functional domain
- **Must**: each class has only one reason to change
- **Must**: separate functionalities with different responsibilities into different classes
- **Forbidden**: creating "god classes" (classes that bear too many responsibilities)

**Function requirements:**

- **Forbidden**: one function doing multiple unrelated things

**Code example:**

```python
# ❌ Bad practice: violates the Single Responsibility Principle
class User:
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    def save_to_database(self):
        """Save the user to the database"""
        pass

    def send_email(self, message: str):
        """Send an email"""
        pass

    def validate_email(self):
        """Validate the email format"""
        pass

# ✅ Good practice: conforms to the Single Responsibility Principle
class User:
    """User data model, only responsible for storing user information"""
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

class UserRepository:
    """User repository, responsible for database operations"""
    def save(self, user: User):
        pass

class EmailService:
    """Email service, responsible for sending emails"""
    def send(self, email: str, message: str):
        pass

class EmailValidator:
    """Email validator, responsible for validating the email format"""
    def validate(self, email: str) -> bool:
        pass
```

### 2. Open/Closed Principle (OCP)

**Principle definition:**
Software entities (classes, modules, functions, etc.) should be open for extension but closed for modification.

**Execution requirements:**

- **Must**: support extension through abstractions and interfaces
- **Must**: be able to add new functionality without changing existing code
- **Forbidden**: modifying tested, stable code in order to add new functionality
- **Must**: use design patterns such as the strategy pattern and template method pattern to support extension

**Implementation methods:**

- Use abstract classes or interfaces to define the specification
- Use inheritance or polymorphism to implement different behaviors
- Use dependency injection to isolate the point of change

**Code example:**

```python
from abc import ABC, abstractmethod
from enum import Enum

# ❌ Bad practice: violates the Open/Closed Principle
class Order:
    def __init__(self, items: list, discount_type: str):
        self.items = items
        self.discount_type = discount_type

    def calculate_total(self) -> float:
        total = sum(item.price for item in self.items)

        # this method needs to be modified every time a new discount type is added
        if self.discount_type == "normal":
            return total * 0.9
        elif self.discount_type == "vip":
            return total * 0.8
        elif self.discount_type == "seasonal":
            return total * 0.7
        # adding a new discount type requires modifying here!

# ✅ Good practice: conforms to the Open/Closed Principle
class DiscountStrategy(ABC):
    """Discount strategy abstract class"""
    @abstractmethod
    def apply_discount(self, total: float) -> float:
        pass

class NormalDiscount(DiscountStrategy):
    def apply_discount(self, total: float) -> float:
        return total * 0.9

class VipDiscount(DiscountStrategy):
    def apply_discount(self, total: float) -> float:
        return total * 0.8

class SeasonalDiscount(DiscountStrategy):
    def apply_discount(self, total: float) -> float:
        return total * 0.7

# adding a new discount type only requires creating a new strategy class, no need to modify the Order class
class NewYearDiscount(DiscountStrategy):
    def apply_discount(self, total: float) -> float:
        return total * 0.5

class Order:
    def __init__(self, items: list, discount_strategy: DiscountStrategy):
        self.items = items
        self.discount_strategy = discount_strategy

    def calculate_total(self) -> float:
        total = sum(item.price for item in self.items)
```

### 3. Liskov Substitution Principle (LSP)

**Principle definition:**

A subclass object must be able to replace a parent class object without breaking the correctness of the program.

**Execution requirements:**

- **Must**: a subclass must fully implement all abstract methods of the parent class
- **Must**: a subclass may extend the parent class's functionality, but must not change the parent class's original functionality
- **Forbidden**: a subclass throwing an exception not declared by the parent class when overriding a parent class method
- **Forbidden**: a subclass weakening the input or output constraints of the parent class method when overriding

**Judgment criteria:**

- A subclass can replace the parent class wherever the parent class appears
- After replacement, the program's behavior should be consistent with using the parent class
**Code example:**

```python
# ❌ Bad practice: violates the Liskov Substitution Principle
class Rectangle:
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def set_width(self, width: float):
        self.width = width

    def set_height(self, height: float):
        self.height = height

    def get_area(self) -> float:
        return self.width * self.height

class Square(Rectangle):
    """A square inherits from a rectangle, but violates the Liskov Substitution Principle"""
    def __init__(self, side: float):
        super().__init__(side, side)

    def set_width(self, width: float):
        self.width = width
        self.height = width  # a square's width and height must be equal

    def set_height(self, height: float):
        self.height = height
        self.width = height  # a square's width and height must be equal

# problem: Square cannot fully replace Rectangle
def process_rectangle(rectangle: Rectangle):
    rectangle.set_width(5)
    rectangle.set_height(4)
    # if a Rectangle is passed in, the area is 20
    # if a Square is passed in, the area is 16 (inconsistent behavior!)
    print(f"area: {rectangle.get_area()}")

# ✅ Good practice: conforms to the Liskov Substitution Principle
from abc import ABC, abstractmethod

class Shape(ABC):
    """Shape abstract base class"""
    @abstractmethod
    def get_area(self) -> float:
        pass

class Rectangle(Shape):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def get_area(self) -> float:
        return self.width * self.height

class Square(Shape):
    """A square no longer inherits from a rectangle; it independently implements the Shape interface"""
    def __init__(self, side: float):
        self.side = side

    def get_area(self) -> float:
        return self.side * self.side

# now both Square and Rectangle can replace Shape
def process_shape(shape: Shape):
    print(f"area: {shape.get_area()}")
```

### 4. Interface Segregation Principle (ISP)

**Principle definition:**
Clients should not depend on interfaces they do not need; interfaces should be small and specific rather than large and all-encompassing.

**Execution requirements:**

- **Must**: split large interfaces into multiple small and specific ones
- **Must**: clients depend only on the interface methods they need
- **Forbidden**: creating "fat interfaces" (interfaces containing a large number of methods)
- **Forbidden**: forcing clients to implement methods they do not need

**Design principles:**

- Interfaces should be split according to functional responsibility
- Each interface should serve a specific client
- Avoid interface pollution

**Code example:**

```python
from abc import ABC, abstractmethod

# ❌ Bad practice: violates the Interface Segregation Principle
class WorkerInterface(ABC):
    """The worker interface contains all possible methods, causing some classes to implement methods they do not need"""
    @abstractmethod
    def work(self):
        pass

    @abstractmethod
    def eat(self):
        pass

    @abstractmethod
    def sleep(self):
        pass

class Robot(WorkerInterface):
    """A robot does not need eat and sleep, but is forced to implement these methods"""
    def work(self):
        print("Robot working")

    def eat(self):
        raise NotImplementedError("A robot does not need to eat")

    def sleep(self):
        raise NotImplementedError("A robot does not need to sleep")

# ✅ Good practice: conforms to the Interface Segregation Principle
class Workable(ABC):
    """Interface for things that can work"""
    @abstractmethod
    def work(self):
        pass

class Eatable(ABC):
    """Interface for things that can eat"""
    @abstractmethod
    def eat(self):
        pass

class Sleepable(ABC):
    """Interface for things that can sleep"""
    @abstractmethod
    def sleep(self):
        pass

class Human(Workable, Eatable, Sleepable):
    """A human implements all interfaces"""
    def work(self):
        print("Human working")

    def eat(self):
        print("Human eating")

    def sleep(self):
        print("Human sleeping")

class Robot(Workable):
    """A robot only implements the interfaces it needs"""
    def work(self):
        print("Robot working")
```

### 5. Dependency Inversion Principle (DIP)

**Principle definition:**

High-level modules should not depend on low-level modules; both should depend on abstractions. Abstractions should not depend on details; details should depend on abstractions.

**Execution requirements:**

- **Must**: both high-level and low-level modules should depend on abstract interfaces
- **Must**: decouple using dependency injection, factory pattern, etc.
- **Forbidden**: high-level modules directly depending on concrete low-level module implementations
- **Forbidden**: directly creating instances of concrete classes inside a module

**Implementation methods:**

- Use abstract classes or interfaces to define the dependency
- Inject dependencies through constructor injection
- Use an inversion of control container to manage dependencies

**Code example:**

```python
# ❌ Bad practice: violates the Dependency Inversion Principle
class LightBulb:
    """Low-level module: light bulb"""
    def turn_on(self):
        print("Light bulb on")

    def turn_off(self):
        print("Light bulb off")

class Switch:
    """High-level module: switch"""
    def __init__(self):
        self.bulb = LightBulb()  # directly depends on a concrete implementation, violating the Dependency Inversion Principle
        self.on = False

    def press(self):
        if self.on:
            self.bulb.turn_off()
            self.on = False
        else:
            self.bulb.turn_on()
            self.on = True

# problem: to use another device (such as a fan), the Switch class must be modified

# ✅ Good practice: conforms to the Dependency Inversion Principle
from abc import ABC, abstractmethod

class Switchable(ABC):
    """Abstract interface: a device that can be switched"""
    @abstractmethod
    def turn_on(self):
        pass

    @abstractmethod
    def turn_off(self):
        pass

class LightBulb(Switchable):
    """A light bulb implements the Switchable interface"""
    def turn_on(self):
        print("Light bulb on")

    def turn_off(self):
        print("Light bulb off")

class Fan(Switchable):
    """A fan implements the Switchable interface"""
    def turn_on(self):
        print("Fan on")

    def turn_off(self):
        print("Fan off")

class Switch:
    """The switch depends on the abstract interface, not the concrete implementation"""
    def __init__(self, device: Switchable):
        self.device = device  # dependency injection
        self.on = False

    def press(self):
        if self.on:
            self.device.turn_off()
            self.on = False
        else:
            self.device.turn_on()
            self.on = True

# usage example
bulb = LightBulb()
switch = Switch(bulb)
switch.press()  # light bulb on

fan = Fan()
switch = Switch(fan)
switch.press()  # fan on
```

## Integrated Application Example

### ❌ An order processing system that violates SOLID

```python
    def __init__(self):
        # violates DIP: directly depends on concrete implementations
        self.database = MySQLDatabase()
        self.email_sender = SMTPSender()
        self.logger = FileLogger()

    def process_order(self, order_data: dict):
        # violates SRP: one method does too many things
        # 1. validate the order
        if not order_data.get('user_id'):
            raise Exception("the user ID cannot be empty")
        if order_data.get('amount', 0) <= 0:
            raise Exception("the amount must be greater than 0")

        # 2. calculate the discount (violates OCP: each new discount requires modifying the code)
        discount = 0
        if order_data.get('user_type') == 'vip':
            discount = 0.1
        elif order_data.get('season') == 'christmas':
            discount = 0.2
        # adding a new discount requires modifying here

        # 3. save the order
        self.database.save_order(order_data)

        # 4. send the email
        self.email_sender.send_email(order_data['user_id'], "order confirmation")

        # 5. record the log
        self.logger.log(f"order processed: {order_data}")
```

### ✅ An order processing system that conforms to SOLID

```python
from abc import ABC, abstractmethod
from typing import Protocol

# ============ abstract interfaces (conform to DIP, ISP) ============

class Database(ABC):
    @abstractmethod
    def save_order(self, order: 'Order') -> None:
        pass

class EmailSender(ABC):
    @abstractmethod
    def send_email(self, user_id: str, message: str) -> None:
        pass

class Logger(ABC):
    @abstractmethod
    def log(self, message: str) -> None:
        pass

class DiscountStrategy(ABC):
    @abstractmethod
    def calculate_discount(self, order: 'Order') -> float:
        pass

class OrderValidator(ABC):
    @abstractmethod
    def validate(self, order: 'Order') -> bool:
        pass

# ============ concrete implementations (conform to SRP) ============

class Order:
    """Order entity: only responsible for storing order data (SRP)"""
    def __init__(self, user_id: str, amount: float, user_type: str, season: str):
        self.user_id = user_id
        self.amount = amount
        self.user_type = user_type
        self.season = season

class OrderValidatorImpl(OrderValidator):
    """Order validator: only responsible for validating the order (SRP)"""
    def validate(self, order: Order) -> bool:
        if not order.user_id:
            raise ValueError("the user ID cannot be empty")
        if order.amount <= 0:
            raise ValueError("the amount must be greater than 0")
        return True

class VipDiscount(DiscountStrategy):
    """VIP discount strategy (SRP + OCP: new strategies can be added independently)"""
    def calculate_discount(self, order: Order) -> float:
        return 0.1 if order.user_type == 'vip' else 0

class SeasonalDiscount(DiscountStrategy):
    """Seasonal discount strategy (SRP + OCP)"""
    def calculate_discount(self, order: Order) -> float:
        return 0.2 if order.season == 'christmas' else 0

class DiscountCalculator:
    """Discount calculator: combines multiple discount strategies (OCP)"""
    def __init__(self, strategies: list[DiscountStrategy]):
        self.strategies = strategies

    def calculate_total_discount(self, order: Order) -> float:
        return sum(strategy.calculate_discount(order) for strategy in self.strategies)

class MySQLDatabase(Database):
    """MySQL database implementation (SRP)"""
    def save_order(self, order: Order) -> None:
        print(f"saving order to MySQL: {order.user_id}")

class SMTPSender(EmailSender):
    """SMTP email sender (SRP)"""
    def send_email(self, user_id: str, message: str) -> None:
        print(f"sending email to {user_id}: {message}")

class FileLogger(Logger):
    """File log recorder (SRP)"""
    def log(self, message: str) -> None:
        print(f"recording log to file: {message}")

class OrderProcessor:
    """Order processor: coordinates each component (SRP + DIP)"""
    def __init__(
        self,
        validator: OrderValidator,
        discount_calculator: DiscountCalculator,
        database: Database,
        email_sender: EmailSender,
        logger: Logger
    ):
        # depends on abstract interfaces, not concrete implementations (DIP)
        self.validator = validator
        self.discount_calculator = discount_calculator
        self.database = database
        self.email_sender = email_sender
        self.logger = logger

    def process_order(self, order: Order) -> None:
        # 1. validate the order
        self.validator.validate(order)

        # 2. calculate the discount
        discount = self.discount_calculator.calculate_total_discount(order)
        final_amount = order.amount * (1 - discount)

        # 3. save the order
        self.database.save_order(order)

        # 4. send the email
        self.email_sender.send_email(order.user_id, f"order confirmation, amount: {final_amount}")

        # 5. record the log
        self.logger.log(f"order processed: {order.user_id}, amount: {final_amount}")

# usage example
validator = OrderValidatorImpl()
discount_calculator = DiscountCalculator([VipDiscount(), SeasonalDiscount()])
database = MySQLDatabase()
email_sender = SMTPSender()
logger = FileLogger()

processor = OrderProcessor(
    validator,
    discount_calculator,
    database,
    email_sender,
    logger
)
order = Order("user123", 1000, "vip", "christmas")
processor.process_order(order)
```

## SOLID Checklist

When writing code, be sure to confirm:

### Single Responsibility Principle (SRP)

- [ ] Each class has only one reason to change
- [ ] Each class bears only one functional domain
- [ ] Each function does only one thing
- [ ] There is no "god class" bearing too many responsibilities
- [ ] Class names and function names accurately reflect their responsibilities

### Open/Closed Principle (OCP)

- [ ] Adding new functionality requires no changes to existing code
- [ ] Abstract classes or interfaces are used to support extension
- [ ] Polymorphism is used to replace large numbers of conditional statements
- [ ] Design patterns (strategy pattern, template method, etc.) are used to support extension
- [ ] Existing code is fully tested, avoiding frequent modification

### Liskov Substitution Principle (LSP)

- [ ] Subclasses can fully replace the parent class
- [ ] Subclasses do not change the parent class's original behavior
- [ ] Subclasses introduce no new constraints when overriding methods
- [ ] Subclasses throw no exceptions not declared by the parent class when overriding methods
- [ ] The inheritance relationship is reasonable, not merely for code reuse

### Interface Segregation Principle (ISP)

- [ ] Interfaces are small and specific, containing no unrelated methods
- [ ] Clients depend only on the interfaces they need
- [ ] No classes are forced to implement methods they do not need
- [ ] Composition is used to replace inheritance to reduce interface dependency
- [ ] Interfaces are split reasonably according to functional responsibility

### Dependency Inversion Principle (DIP)

- [ ] High-level modules depend on abstract interfaces, not concrete implementations
- [ ] Low-level modules implement abstract interfaces
- [ ] Dependency injection is used to pass dependencies
- [ ] No concrete class instances are directly created inside modules
- [ ] The factory pattern or an inversion of control container is used to manage dependencies

### Comprehensive Assessment

- [ ] The code structure is clear and easy to understand and maintain
- [ ] The code has good extensibility
- [ ] Unit tests are easy to write and execute
- [ ] The coupling between modules is low
- [ ] The code conforms to the project's design conventions and best practices
