class OrderItem < ApplicationRecord
  belongs_to :order
  belongs_to :product

  validates :quantity, presence: true, numericality: { greater_than: 0 }
  validates :unit_price_cents, presence: true, numericality: { greater_than_or_equal_to: 0 }
  validates :discount_percent, presence: true, numericality: { 
    only_integer: true, 
    greater_than_or_equal_to: 0, 
    less_than_or_equal_to: 100 
  }

  before_validation :order_is_pending, on: [:create, :update]
  before_destroy :ensure_order_is_pending

  before_validation :copy_product_price, on: :create
  after_save :recalculate_order_total
  after_destroy :recalculate_order_total

  def line_total_cents
    (unit_price_cents * quantity * (1 - discount_percent / 100)).round
  end

  private

  def copy_product_price
    self.unit_price_cents = product.price_cents if product && (unit_price_cents.nil? || unit_price_cents.zero?)
  end

  def recalculate_order_total
    order&.recalculate_total!
  end

  def order_is_pending
    return if order.nil? || order.pending?

    raise InvalidStateTransitionError, "Cannot modify order items unless order is pending (current status: #{order.status})"
  end

  def ensure_order_is_pending
    return if order.nil? || order.pending?

    raise InvalidStateTransitionError, "Cannot delete order items unless order is pending (current status: #{order.status})"
  end
end
