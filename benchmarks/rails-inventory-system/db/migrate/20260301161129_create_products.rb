class CreateProducts < ActiveRecord::Migration[8.0]
  def change
    create_table :products do |t|
      t.string :name, null: false
      t.string :sku, null: false
      t.integer :price_cents, null: false, default: 0

      t.timestamps
    end
    add_index :products, :name, unique: true
    add_index :products, :sku, unique: true
    add_check_constraint :products, "price_cents >= 0", name: "price_cents_non_negative"
  end
end
