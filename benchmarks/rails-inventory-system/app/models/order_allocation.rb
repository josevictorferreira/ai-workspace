class OrderAllocation < ApplicationRecord
  belongs_to :order
  belongs_to :product
  belongs_to :warehouse

  validates :quantity, presence: true, numericality: { greater_than: 0 }
end
