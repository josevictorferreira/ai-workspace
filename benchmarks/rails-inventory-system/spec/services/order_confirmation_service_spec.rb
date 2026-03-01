require 'rails_helper'

RSpec.describe OrderConfirmationService do
  let(:product) { create(:product, price_cents: 100) }
  let(:w1) { create(:warehouse, id: 1) }
  let(:w2) { create(:warehouse, id: 2) }
  let(:order) { create(:order) }
  let!(:item) { create(:order_item, order: order, product: product, quantity: 15) }

  describe '#call' do
    context 'when sufficient stock in single warehouse' do
      before do
        create(:inventory_item, product: product, warehouse: w1, quantity: 20)
      end

      it 'confirms the order and deducts stock' do
        OrderConfirmationService.new(order).call
        expect(order.reload.status).to eq('confirmed')
        expect(InventoryItem.find_by(product: product, warehouse: w1).quantity).to eq(5)
      end
    end

    context 'when stock split across warehouses' do
      before do
        create(:inventory_item, product: product, warehouse: w1, quantity: 10)
        create(:inventory_item, product: product, warehouse: w2, quantity: 10)
      end

      it 'deducts from warehouses in ascending ID order' do
        OrderConfirmationService.new(order).call
        expect(order.reload.status).to eq('confirmed')
        expect(InventoryItem.find_by(product: product, warehouse: w1).quantity).to eq(0)
        expect(InventoryItem.find_by(product: product, warehouse: w2).quantity).to eq(5)
      end

      it 'creates order allocations' do
        OrderConfirmationService.new(order).call
        expect(order.order_allocations.count).to eq(2)
        expect(order.order_allocations.find_by(warehouse: w1).quantity).to eq(10)
        expect(order.order_allocations.find_by(warehouse: w2).quantity).to eq(5)
      end
    end

    context 'when insufficient stock' do
      before do
        create(:inventory_item, product: product, warehouse: w1, quantity: 5)
        create(:inventory_item, product: product, warehouse: w2, quantity: 5)
      end

      it 'raises InsufficientStockError and rolls back stock deduction' do
        expect { OrderConfirmationService.new(order).call }.to raise_error(InsufficientStockError)
        expect(order.reload.status).to eq('pending')
        expect(InventoryItem.find_by(product: product, warehouse: w1).quantity).to eq(5)
        expect(InventoryItem.find_by(product: product, warehouse: w2).quantity).to eq(5)
      end
    end

    context 'when order is already confirmed' do
      it 'raises InvalidStateTransitionError' do
        order.update!(status: 'confirmed')
        expect { OrderConfirmationService.new(order).call }.to raise_error(InvalidStateTransitionError)
      end
    end

    context 'when order has no items' do
      it 'raises error' do
        empty_order = create(:order)
        expect { OrderConfirmationService.new(empty_order).call }.to raise_error(StandardError, "Cannot confirm order with no items")
      end
    end
  end
end
