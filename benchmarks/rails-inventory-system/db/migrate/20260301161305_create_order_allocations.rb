class CreateOrderAllocations < ActiveRecord::Migration[8.1]
  def change
    create_table :order_allocations do |t|
      t.references :order, null: false, foreign_key: true
      t.references :product, null: false, foreign_key: true
      t.references :warehouse, null: false, foreign_key: true
      t.integer :quantity

      t.timestamps
    end
  end
end
