class CreateInventoryItems < ActiveRecord::Migration[8.0]
  def change
    create_table :inventory_items do |t|
      t.references :product, null: false, foreign_key: true
      t.references :warehouse, null: false, foreign_key: true
      t.integer :quantity, null: false, default: 0

      t.timestamps
    end
    add_index :inventory_items, [:product_id, :warehouse_id], unique: true
    add_check_constraint :inventory_items, "quantity >= 0", name: "quantity_non_negative"
  end
end
