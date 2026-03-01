class CreateOrders < ActiveRecord::Migration[8.0]
  def change
    create_table :orders do |t|
      t.string :status, null: false, default: "pending"
      t.integer :total_cents, null: false, default: 0

      t.timestamps
    end
    add_index :orders, :status
    add_check_constraint :orders, "total_cents >= 0", name: "total_cents_non_negative"
  end
end
