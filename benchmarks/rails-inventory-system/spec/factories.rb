FactoryBot.define do
  factory :product do
    sequence(:name) { |n| "Product #{n}" }
    sequence(:sku) { |n| "SKU-#{n}" }
    price_cents { 1000 }
  end

  factory :warehouse do
    sequence(:name) { |n| "Warehouse #{n}" }
  end

  factory :inventory_item do
    product
    warehouse
    quantity { 100 }
  end

  factory :order do
    status { "pending" }
    total_cents { 0 }
  end

  factory :order_item do
    order
    product
    quantity { 1 }
    discount_percent { 0 }
  end
end
