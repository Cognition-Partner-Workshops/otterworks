require 'rails_helper'

RSpec.describe FinanceWarehouse::DashboardQueries do
  subject(:queries) { described_class.new(client: client) }

  let(:client) { instance_double(FinanceWarehouse::TeradataClient) }
  let(:summary) { { 'DSO' => '27.00', 'AR_OPEN_BALANCE' => '45000.00', 'COLLECTIONS_30_DAYS' => '32000.00' } }
  let(:account) do
    {
      'ACCOUNT_NO' => 'A000318274 ', 'CUSTOMER_NAME' => 'Bramblewood Outfitters',
      'OLDEST_DUE_DATE' => Date.new(2025, 10, 15), 'OVERDUE_BALANCE' => '12000.50'
    }
  end

  before do
    allow(described_class).to receive(:enabled?).and_return(true)
    allow(client).to receive(:query).with(described_class::SUMMARY_SQL).and_return([summary])
    allow(client).to receive(:query).with(described_class::OVERDUE_SQL).and_return([account])
  end

  it 'maps summary amounts and overdue account values' do
    result = queries.call
    expect(result).to include(dso: '27.0', ar_open_balance: '45000.0', collections_30_days: '32000.0')
    expect(result[:top_overdue_accounts]).to eq([{
      account_no: 'A000318274', customer_name: 'Bramblewood Outfitters',
      oldest_due_date: '2025-10-15', overdue_balance: '12000.5'
    }])
  end

  it 'returns an empty account list and zero summary for an empty warehouse' do
    allow(client).to receive(:query).with(described_class::SUMMARY_SQL).and_return([
      { 'DSO' => 0, 'AR_OPEN_BALANCE' => 0, 'COLLECTIONS_30_DAYS' => 0 }
    ])
    allow(client).to receive(:query).with(described_class::OVERDUE_SQL).and_return([])
    expect(queries.call).to eq(
      dso: '0.0', ar_open_balance: '0.0', collections_30_days: '0.0', top_overdue_accounts: []
    )
  end

  it 'rejects disabled access before querying or reading cached data' do
    allow(described_class).to receive(:enabled?).and_return(false)
    expect(client).not_to receive(:query)
    expect { queries.dashboard }.to raise_error(described_class::Disabled)
  end

  it 'propagates warehouse errors' do
    allow(client).to receive(:query).and_raise(FinanceWarehouse::TeradataClient::Unavailable)
    expect { queries.call }.to raise_error(FinanceWarehouse::TeradataClient::Unavailable)
  end

  it 'refreshes the cache and reuses the dashboard cache' do
    cache = ActiveSupport::Cache::MemoryStore.new
    allow(Rails).to receive(:cache).and_return(cache)
    refreshed = queries.refresh
    expect(cache.read(described_class::CACHE_KEY)).to eq(refreshed)
    expect(client).not_to receive(:query)
    expect(queries.dashboard).to eq(refreshed)
  end
end
