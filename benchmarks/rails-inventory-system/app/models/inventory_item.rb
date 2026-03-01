class InventoryItem < ApplicationRecord
  belongs_to :product
  belongs_to :warehouse

  validates :quantity, presence: true, numericality: { greater_than_or_equal_to: 0 }
  validates :product_id, uniqueness: { scope: :warehouse_id }
end
