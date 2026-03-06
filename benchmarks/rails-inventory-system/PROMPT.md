## Project Context

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

See full details in AGENTS.md.

## Current Branch

You are working on the `v1/failing` branch.

## Task

Fix the failing tests so that `bundle exec rspec` passes.

- Do NOT change the intended business logic or introduce scope creep.
- Do NOT modify database.yml or change database configuration.
- Focus only on fixing the failing test cases.
- Make minimal changes to get tests passing.
- Do not run any git commands, the user will handle commits and branch management, you can't even.

## Instructions

1. Identify the root cause of the failures.
2. Make the minimal code changes needed to fix the tests.
3. Run `bundle exec rspec` to verify your fixes.

Do not ask the user questions - work autonomously.
