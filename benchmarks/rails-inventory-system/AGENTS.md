# AGENTS.md

## Project Overview

This is a **Ruby on Rails 8.1 API-only** application implementing an **Order and Inventory Management System**. The system manages products, warehouses, and inventory stock, handling the full lifecycle of an order from pending to confirmed or cancelled.

### Key Features
- **Multi-Warehouse Support**: Inventory is tracked per warehouse.
- **Stock Allocation Logic**: Orders are confirmed by deducting stock from warehouses in ascending ID order.
- **Atomic Transactions**: Inventory deductions and order status updates are performed within database transactions to ensure data integrity.
- **Inventory Restoration**: Cancelling a confirmed order accurately restores stock to the original warehouses using an allocation tracking system.
- **State Integrity**: Strict guards prevent modifying orders once they are confirmed or cancelled.
- **Deterministic Business Logic**: All line total and order total calculations are performed within the application domain.

### Tech Stack
- **Language**: Ruby 3.x
- **Framework**: Rails 8.1 (API-only mode)
- **Database**: PostgreSQL
- **Testing**: RSpec, FactoryBot, Shoulda Matchers

---

## Building and Running

### Prerequisites
- Ruby 3.x
- PostgreSQL

### Setup
```bash
# Install dependencies
bundle install

# Setup database (create, migrate, seed)
bin/setup
```

### Running the Application
```bash
bin/rails server
```

### Running Tests
```bash
# Run all tests
bundle exec rspec

# Run specific tests
bundle exec rspec spec/models/order_spec.rb
bundle exec rspec spec/services/order_confirmation_service_spec.rb
```

---

## Development Conventions

### Architecture
- **Service Objects**: Complex business logic (confirmation, cancellation) is encapsulated in service objects located in `app/services/`.
- **Domain Errors**: Custom error classes are used for business rule violations to provide clear, actionable feedback.
    - `InsufficientStockError`: Raised when inventory is insufficient for confirmation.
    - `InvalidStateTransitionError`: Raised when attempting invalid status changes or modifying confirmed/cancelled orders.
- **Database Constraints**: Data integrity is reinforced at the database level using `CHECK` constraints and `UNIQUE` indexes.

### Models and Logic
- **`Order`**: Manages status and total cents.
- **`OrderItem`**: Calculates line totals (price * quantity * discount) and triggers order total recalculation. Prevents modifications if the parent order is not `pending`.
- **`InventoryItem`**: Tracks stock quantity and ensures non-negative values via DB constraints.
- **`OrderAllocation`**: Internal tracking model used to record exactly which warehouse stock was taken from during confirmation, enabling precise restoration on cancellation.

### Testing Practices
- **RSpec**: Comprehensive test coverage for models and services.
- **Factories**: Use `FactoryBot` in `spec/factories.rb` for test data generation.
- **Transactional Tests**: RSpec is configured to run each test in a transaction to maintain a clean database state.
