require 'rails_helper'

RSpec.describe Order, type: :model do
  describe 'validations' do
    it { is_expected.to validate_presence_of(:status) }
    it { is_expected.to validate_inclusion_of(:status).in_array(%w[pending confirmed cancelled]) }
    it { is_expected.to validate_numericality_of(:total_cents).is_greater_than_or_equal_to(0) }
  end

  describe '#recalculate_total!' do
    let(:product) { create(:product, price_cents: 100) }
    let(:order) { create(:order) }

    it 'calculates the sum of order items totals' do
      create(:order_item, order: order, product: product, quantity: 2, discount_percent: 0) # 200
      create(:order_item, order: order, product: product, quantity: 1, discount_percent: 50) # 50
      
      order.recalculate_total!
      expect(order.total_cents).to eq(250)
    end
  end
end
