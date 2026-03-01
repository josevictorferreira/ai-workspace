class Product < ApplicationRecord
  has_many :inventory_items, dependent: :destroy
  has_many :order_items, dependent: :destroy

  validates :name, presence: true, uniqueness: true
  validates :sku, presence: true, uniqueness: true
  validates :price_cents, presence: true, numericality: { greater_than_or_equal_to: 0 }
end
