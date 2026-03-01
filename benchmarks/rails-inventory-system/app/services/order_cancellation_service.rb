class OrderCancellationService
  def initialize(order)
    @order = order
  end

  def call
    raise InvalidStateTransitionError, "Order is already cancelled" if @order.cancelled?

    Order.transaction do
      if @order.confirmed?
        restore_inventory
      end
      @order.update!(status: "cancelled")
    end
  end

  private

  def restore_inventory
    @order.order_allocations.each do |allocation|
      inventory_item = InventoryItem.find_or_initialize_by(
        product: allocation.product,
        warehouse: allocation.warehouse
      )
      inventory_item.increment!(:quantity, allocation.quantity)
    end
    @order.order_allocations.destroy_all
  end
end
