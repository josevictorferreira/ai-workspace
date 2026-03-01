require 'rails_helper'

RSpec.describe OrderCancellationService do
  let(:product) { create(:product, price_cents: 100) }
  let(:w1) { create(:warehouse, id: 1) }
  let(:w2) { create(:warehouse, id: 2) }
  let(:order) { create(:order) }
  let!(:item) { create(:order_item, order: order, product: product, quantity: 15) }

  describe '#call' do
    context 'when order is pending' do
      it 'marks order as cancelled' do
        OrderCancellationService.new(order).call
        expect(order.reload.status).to eq('cancelled')
      end
    end

    context 'when order is confirmed' do
      before do
        create(:inventory_item, product: product, warehouse: w1, quantity: 10)
        create(:inventory_item, product: product, warehouse: w2, quantity: 10)
        OrderConfirmationService.new(order).call
      end

      it 'restores inventory to original warehouses' do
        expect(InventoryItem.find_by(product: product, warehouse: w1).quantity).to eq(0)
        expect(InventoryItem.find_by(product: product, warehouse: w2).quantity).to eq(5)

        OrderCancellationService.new(order).call
        expect(order.reload.status).to eq('cancelled')
        expect(InventoryItem.find_by(product: product, warehouse: w1).quantity).to eq(10)
        expect(InventoryItem.find_by(product: product, warehouse: w2).quantity).to eq(10)
      end

      it 'removes order allocations' do
        OrderCancellationService.new(order).call
        expect(order.order_allocations.count).to eq(0)
      end
    end

    context 'when order is already cancelled' do
      it 'raises InvalidStateTransitionError' do
        order.update!(status: 'cancelled')
        expect { OrderCancellationService.new(order).call }.to raise_error(InvalidStateTransitionError)
      end
    end
  end
end
