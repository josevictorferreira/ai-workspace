require 'rails_helper'

RSpec.describe OrderItem, type: :model do
  describe 'validations' do
    it { is_expected.to validate_numericality_of(:quantity).is_greater_than(0) }
    it { is_expected.to validate_numericality_of(:discount_percent).only_integer.is_greater_than_or_equal_to(0).is_less_than_or_equal_to(100) }
  end

  describe 'callbacks' do
    let(:product) { create(:product, price_cents: 500) }
    let(:order) { create(:order) }

    it 'copies product price on creation' do
      item = create(:order_item, order: order, product: product)
      expect(item.unit_price_cents).to eq(500)
    end

    it 'recalculates order total after save' do
      expect(order.total_cents).to eq(0)
      create(:order_item, order: order, product: product, quantity: 2)
      expect(order.reload.total_cents).to eq(1000)
    end

    it 'prevents modification if order is not pending' do
      order.update!(status: 'confirmed')
      item = order.order_items.build(product: product)
      expect { item.valid? }.to raise_error(InvalidStateTransitionError)
    end

    it 'prevents deletion if order is not pending' do
      item = create(:order_item, order: order, product: product)
      order.update!(status: 'confirmed')
      expect { item.destroy }.to raise_error(InvalidStateTransitionError)
    end
  end

  describe '#line_total_cents' do
    it 'calculates total with discount' do
      item = build(:order_item, unit_price_cents: 100, quantity: 10, discount_percent: 10)
      expect(item.line_total_cents).to eq(900)
    end

    it 'rounds to nearest integer' do
      item = build(:order_item, unit_price_cents: 100, quantity: 1, discount_percent: 33)
      # 100 * 1 * 0.67 = 67
      expect(item.line_total_cents).to eq(67)

      # 10 * 7 * (1 - 0.05) = 70 * 0.95 = 66.5 -> should be 67
      item2 = build(:order_item, unit_price_cents: 10, quantity: 7, discount_percent: 5)
      expect(item2.line_total_cents).to eq(67)
    end
  end
end
