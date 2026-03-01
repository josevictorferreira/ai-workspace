class CreateOrderItems < ActiveRecord::Migration[8.0]
  def change
    create_table :order_items do |t|
      t.references :order, null: false, foreign_key: true
      t.references :product, null: false, foreign_key: true
      t.integer :quantity, null: false, default: 1
      t.integer :unit_price_cents, null: false, default: 0
      t.integer :discount_percent, null: false, default: 0

      t.timestamps
    end
    add_check_constraint :order_items, "quantity > 0", name: "quantity_positive"
    add_check_constraint :order_items, "discount_percent >= 0 AND discount_percent <= 100", name: "discount_percent_range"
  end
end
