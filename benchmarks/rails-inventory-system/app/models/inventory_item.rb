class InventoryItem < ApplicationRecord
  belongs_to :product
  belongs_to :warehouse

  validates :quantity, presence: true
  validates :product_id, uniqueness: { scope: :warehouse_id }
end
