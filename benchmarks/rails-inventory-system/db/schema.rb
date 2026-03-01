# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# This file is the source Rails uses to define your schema when running `bin/rails
# db:schema:load`. When creating a new database, `bin/rails db:schema:load` tends to
# be faster and is potentially less error prone than running all of your
# migrations from scratch. Old migrations may fail to apply correctly if those
# migrations use external dependencies or application code.
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema[8.1].define(version: 2026_03_01_161305) do
  # These are extensions that must be enabled in order to support this database
  enable_extension "pg_catalog.plpgsql"

  create_table "inventory_items", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.bigint "product_id", null: false
    t.integer "quantity", default: 0, null: false
    t.datetime "updated_at", null: false
    t.bigint "warehouse_id", null: false
    t.index ["product_id", "warehouse_id"], name: "index_inventory_items_on_product_id_and_warehouse_id", unique: true
    t.index ["product_id"], name: "index_inventory_items_on_product_id"
    t.index ["warehouse_id"], name: "index_inventory_items_on_warehouse_id"
    t.check_constraint "quantity >= 0", name: "quantity_non_negative"
  end

  create_table "order_allocations", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.bigint "order_id", null: false
    t.bigint "product_id", null: false
    t.integer "quantity"
    t.datetime "updated_at", null: false
    t.bigint "warehouse_id", null: false
    t.index ["order_id"], name: "index_order_allocations_on_order_id"
    t.index ["product_id"], name: "index_order_allocations_on_product_id"
    t.index ["warehouse_id"], name: "index_order_allocations_on_warehouse_id"
  end

  create_table "order_items", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.integer "discount_percent", default: 0, null: false
    t.bigint "order_id", null: false
    t.bigint "product_id", null: false
    t.integer "quantity", default: 1, null: false
    t.integer "unit_price_cents", default: 0, null: false
    t.datetime "updated_at", null: false
    t.index ["order_id"], name: "index_order_items_on_order_id"
    t.index ["product_id"], name: "index_order_items_on_product_id"
    t.check_constraint "discount_percent >= 0 AND discount_percent <= 100", name: "discount_percent_range"
    t.check_constraint "quantity > 0", name: "quantity_positive"
  end

  create_table "orders", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.string "status", default: "pending", null: false
    t.integer "total_cents", default: 0, null: false
    t.datetime "updated_at", null: false
    t.index ["status"], name: "index_orders_on_status"
    t.check_constraint "total_cents >= 0", name: "total_cents_non_negative"
  end

  create_table "products", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.string "name", null: false
    t.integer "price_cents", default: 0, null: false
    t.string "sku", null: false
    t.datetime "updated_at", null: false
    t.index ["name"], name: "index_products_on_name", unique: true
    t.index ["sku"], name: "index_products_on_sku", unique: true
    t.check_constraint "price_cents >= 0", name: "price_cents_non_negative"
  end

  create_table "warehouses", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.string "name", null: false
    t.datetime "updated_at", null: false
    t.index ["name"], name: "index_warehouses_on_name", unique: true
  end

  add_foreign_key "inventory_items", "products"
  add_foreign_key "inventory_items", "warehouses"
  add_foreign_key "order_allocations", "orders"
  add_foreign_key "order_allocations", "products"
  add_foreign_key "order_allocations", "warehouses"
  add_foreign_key "order_items", "orders"
  add_foreign_key "order_items", "products"
end
