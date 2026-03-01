class Order < ApplicationRecord
  STATUSES = %w[pending confirmed cancelled].freeze

  has_many :order_items, dependent: :destroy
  has_many :order_allocations, dependent: :destroy

  validates :status, presence: true, inclusion: { in: STATUSES }
  validates :total_cents, presence: true, numericality: { greater_than_or_equal_to: 0 }

  def recalculate_total!
    self.total_cents = order_items.reload.sum(&:line_total_cents)
    save!
  end

  def pending?
    status == "pending"
  end

  def confirmed?
    status == "confirmed"
  end

  def cancelled?
    status == "cancelled"
  end

  def can_modify?
    pending?
  end
end
