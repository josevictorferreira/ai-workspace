class Warehouse < ApplicationRecord
  has_many :inventory_items, dependent: :destroy

  validates :name, presence: true, uniqueness: true
end
