require 'rails_helper'

RSpec.describe InventoryItem, type: :model do
  describe 'validations' do
    subject { create(:inventory_item) }

    it { is_expected.to validate_numericality_of(:quantity).is_greater_than_or_equal_to(0) }
    it { is_expected.to validate_uniqueness_of(:product_id).scoped_to(:warehouse_id) }
  end
end
