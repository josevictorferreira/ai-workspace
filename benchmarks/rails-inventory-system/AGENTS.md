# Rails Inventory System

This is a Ruby on Rails 8.1 API-only application that implements an Order Inventory Management System. It is used as a benchmark target: an LLM agent is given failing tests and must fix the implementation while preserving the intended business rules.

## Project Overview

The system manages products, warehouses, and inventory stock. It handles the full lifecycle of an order from `pending` through `confirmed` to `cancelled`.

### Key Features

- **Multi-Warehouse Support**: Inventory is tracked per warehouse.
- **Stock Allocation Logic**: Confirmed orders deduct stock from warehouses in ascending order.
- **Atomic Transactions**: Inventory deductions and order-status updates run inside database transactions.
- **Inventory Restoration**: Cancelling a confirmed order restores stock to the original warehouses using allocation tracking.
- **State Integrity**: Guards prevent modifying orders once they are confirmed or cancelled.
- **Deterministic Business Logic**: All line totals and order totals are calculated in the application domain.

### Tech Stack

- **Language**: Ruby 3.x
- **Framework**: Rails 8.1 (API-only mode)
- **Database**: PostgreSQL
- **Testing**: RSpec, FactoryBot, Shoulda Matchers

## Building and Running

### Prerequisites

- Nix with flakes enabled, or Ruby 3.x and PostgreSQL installed locally
- API key for the benchmark runner

### Setup

```bash
cd benchmarks/rails-inventory-system
nix develop

# Install gems and set up the database
bundle install
bin/setup
```

### Running the Application

```bash
bin/rails server
```

### Running Tests

```bash
# All tests
bundle exec rspec

# Specific files
bundle exec rspec spec/models/order_spec.rb
bundle exec rspec spec/services/order_confirmation_service_spec.rb
```

## Benchmarking

This project is primarily exercised through benchmark runners that check out a failing branch, let an LLM fix it, and then run the test suite.

```bash
# Automated fast benchmark (single branch)
make benchmark MODEL=openrouter/openai/gpt-4o

# Interactive manual benchmark
make benchmark-manual

# Clean artifacts for a model
make clean-benchmark MODEL=openrouter/openai/gpt-4o
```

Results are written to `.sisyphus/benchmark-results-fast.md` or `.sisyphus/benchmark-results.md`.

### Benchmark Files

- `bin/benchmark-runner` — full multi-branch benchmark
- `bin/benchmark-runner-fast` — fast single-branch benchmark (v1/failing)
- `bin/benchmark-interactive` — interactive manual session
- `PROMPT.md` — task description given to the LLM
- `BENCHMARK_GUIDE.md` — detailed runner instructions

## Architecture Notes

- **Models**: `Product`, `Warehouse`, `InventoryStock`, `Order`, `OrderLine`, `StockAllocation`
- **Services**: `OrderConfirmationService` and `OrderCancellationService` encapsulate state transitions.
- **Controllers**: API-only controllers under `app/controllers/`.
- **Database**: Migrations are in `db/migrate/`; seed data is in `db/seeds.rb`.

## Development Guidelines

1. **Use the Nix shell**: `nix develop` provides Ruby, PostgreSQL, and helper scripts.
2. **Keep business logic in services**: Do not scatter confirmation/cancellation logic across controllers or callbacks.
3. **Maintain transaction boundaries**: Stock changes and status changes must remain atomic.
4. **Preserve state guards**: Once an order is `confirmed` or `cancelled`, it should not be editable through normal endpoints.
5. **Run the full RSpec suite** before considering a change complete.
6. **Benchmark responsibly**: The benchmark runners create Git worktrees and branches. Review `make clean-benchmark` before running it to avoid losing wanted results.

## Common Gotchas

- PostgreSQL must be running and reachable before `bin/setup` or tests will work. The Nix shell may provide a local PostgreSQL helper; check `flake.nix` for `db_reset`, `db_parallel_create`, and `db_parallel_drop`.
- Parallel test databases are created/dropped with helper scripts based on `nproc`.
- The benchmark branch `v1/fix/$(MODEL_SLUG)` is created and reused; clean it between runs if you want a fresh start.
- Do not commit API keys or `.sisyphus/` benchmark outputs.
