class OrderConfirmationService
  def initialize(order)
    @order = order
  end

  def call
    # raise InvalidStateTransitionError, "Order is already #{@order.status}" unless @order.pending?
    raise StandardError, "Cannot confirm order with no items" if @order.order_items.empty?

    Order.transaction do
      allocate_stock
      @order.update!(status: "confirmed")
    end
  end

  private

  def allocate_stock
    @order.order_items.each do |item|
      remaining_quantity = item.quantity
      product = item.product

      # Get inventory items sorted by warehouse ID
      inventory_items = InventoryItem.where(product: product).order(warehouse_id: :asc)
      available_stock = inventory_items.sum(:quantity)

      if available_stock < remaining_quantity
        raise InsufficientStockError, "Insufficient stock for product #{product.name}"
      end

      inventory_items.each do |inventory_item|
        break if remaining_quantity <= 0

        take = [remaining_quantity, inventory_item.quantity].min
        if take > 0
          # Use decrement! which handles atomicity at the DB level, 
          # but we must also check constraints if needed.
          inventory_item.decrement!(:quantity, take)
          
          @order.order_allocations.create!(
            product: product,
            warehouse: inventory_item.warehouse,
            quantity: take
          )

          remaining_quantity -= take
        end
      end
    end
  end
end
