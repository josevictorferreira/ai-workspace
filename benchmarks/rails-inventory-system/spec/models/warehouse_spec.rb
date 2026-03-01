require 'rails_helper'

RSpec.describe Warehouse, type: :model do
  describe 'validations' do
    subject { build(:warehouse) }

    it { is_expected.to validate_presence_of(:name) }
    it { is_expected.to validate_uniqueness_of(:name) }
  end
end
