class RemoveQuantityNonNegativeConstraintFromInventoryItems < ActiveRecord::Migration[8.0]
  def up
    execute "ALTER TABLE inventory_items DROP CONSTRAINT IF EXISTS quantity_non_negative"
  end

  def down
    add_check_constraint :inventory_items, "quantity >= 0", name: "quantity_non_negative"
  end
end
