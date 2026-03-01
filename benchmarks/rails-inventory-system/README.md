# Rails Order and Inventory Management System

A robust Ruby on Rails application implementing an Order and Inventory Management System with deterministic business logic, multi-warehouse support, and full RSpec test coverage.

## Features

- **Product Management**: Tracks products with unique names, SKUs, and prices.
- **Multi-Warehouse Inventory**: Tracks stock levels per product across multiple warehouses.
- **Order Lifecycle**:
  - **Pending**: Initial state where items can be added or removed.
  - **Confirmed**: Stock is reserved and deducted across warehouses using a deterministic allocation rule.
  - **Cancelled**: Stock is restored to the original warehouses if the order was confirmed.
- **Deterministic Stock Allocation**: Stock is deducted from warehouses in ascending ID order until the quantity is fulfilled.
- **Atomic Transactions**: All inventory mutations and status updates are wrapped in database transactions to ensure data integrity.
- **Domain-Driven Design**: Logic is encapsulated in Service Objects and custom Domain Errors.
- **Data Integrity**: Enforced through both Rails validations and PostgreSQL `CHECK` constraints.

## Requirements

- **Ruby**: 3.x
- **Rails**: 8.1.x
- **Database**: PostgreSQL

## Setup

1. **Install Dependencies**:
   ```bash
   bundle install
   ```

2. **Database Setup**:
   Ensure PostgreSQL is running, then run:
   ```bash
   bin/setup
   ```

## Running Tests

The project uses RSpec for testing. All business rules, including multi-warehouse allocation and restoration, are fully covered.

```bash
bundle exec rspec
```

## Business Logic & Rules

### Order Confirmation
When an order is confirmed:
- The system verifies sufficient stock exists across all warehouses.
- Stock is deducted from the first available warehouse (sorted by ID).
- If one warehouse is insufficient, it continues to the next.
- An `OrderAllocation` record is created to track exactly where the stock was taken from.

### Order Cancellation
- If a confirmed order is cancelled, the system uses the `OrderAllocation` records to restore stock to the exact warehouses it was originally taken from.

### Constraints
- **Negative Stock**: Prevented at the database level.
- **Modifications**: Orders cannot be modified (items added/removed/updated) once they are confirmed or cancelled.
- **Totals**: Order totals are automatically recalculated whenever an item is added, updated, or removed.

## Architecture

- **Models**: Located in `app/models/`.
- **Services**: Located in `app/services/`.
  - `OrderConfirmationService`: Handles the confirmation and stock allocation logic.
  - `OrderCancellationService`: Handles the cancellation and stock restoration logic.
- **Custom Errors**: `InsufficientStockError` and `InvalidStateTransitionError`.
- **Factories**: Located in `spec/factories.rb`.
