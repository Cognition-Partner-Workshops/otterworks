require 'rails_helper'

RSpec.describe MetricsAggregator do
  it 'returns zero storage usage with no quotas' do
    expect(described_class.storage_metrics).to include(average_usage_percent: 0, total_allocated_bytes: 0, total_used_bytes: 0)
  end

  it 'ignores legacy zero denominators when averaging usage' do
    zero = create(:storage_quota)
    zero.update_column(:quota_bytes, 0)
    create(:storage_quota, quota_bytes: 100, used_bytes: 25)
    expect(described_class.storage_metrics[:average_usage_percent]).to eq(25)
  end

  it 'returns zero rather than null when every quota has a zero denominator' do
    quota = create(:storage_quota)
    quota.update_column(:quota_bytes, 0)
    expect(described_class.storage_metrics[:average_usage_percent]).to eq(0)
  end
end
