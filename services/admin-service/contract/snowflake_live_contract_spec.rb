require_relative 'spec_helper'

RSpec.describe 'admin-service on live Snowflake' do
  before(:all) do
    @warehouse = ContractWarehouse::SnowflakeWarehouse.new if ContractWarehouse::SnowflakeWarehouse.configured?
  end

  before do
    skip 'Snowflake credentials not configured' unless @warehouse
  end

  after(:all) do
    puts "\nSnowflake query IDs: #{@warehouse.query_ids.join(', ')}" if @warehouse
  end

  let(:parity) { JSON.parse(File.read(File.join(ContractWarehouse::ROOT, 'expected', 'snowflake-live.json'))) }
  let(:binds) { [ContractWarehouse::AS_OF.iso8601] }

  def recorded(query)
    JSON.parse(File.read(File.join(ContractWarehouse::ROOT, 'recorded', 'teradata', "#{query}.json")))
  end

  it 'returns the dashboard summary shape and the collections the emulator returns' do
    rows = @warehouse.query(FinanceWarehouse::DashboardQueries::SUMMARY_SQL, binds)
    expected = parity.dig('must_agree', 'dashboard-summary')
    expect(rows.length).to eq(expected.fetch('row_count'))
    expect(rows.first.keys).to eq(recorded('dashboard-summary').fetch('columns'))
    expected.fetch('values').each do |column, value|
      expect(BigDecimal(rows.first.fetch(column))).to eq(BigDecimal(value))
    end
    expect(BigDecimal(rows.first.fetch('AR_OPEN_BALANCE'))).to be_positive
    expect(BigDecimal(rows.first.fetch('DSO'))).to be_positive
  end

  it 'returns the top overdue accounts in the legacy shape and order' do
    rows = @warehouse.query(FinanceWarehouse::DashboardQueries::OVERDUE_SQL, binds)
    expect(rows.length).to eq(parity.dig('must_agree', 'overdue-accounts', 'row_count'))
    expect(rows.first.keys).to eq(recorded('overdue-accounts').fetch('columns'))
    balances = rows.map { |row| BigDecimal(row.fetch('OVERDUE_BALANCE')) }
    expect(balances).to eq(balances.sort.reverse)
    expect(balances).to all(be_positive)
    rows.each do |row|
      expect(row.fetch('ACCOUNT_NO')).to match(/\AACC-\d+\z/)
      expect(row.fetch('OLDEST_DUE_DATE')).to match(/\A\d{4}-\d{2}-\d{2}\z/)
      expect(Date.iso8601(row.fetch('OLDEST_DUE_DATE'))).to be < ContractWarehouse::AS_OF
    end
  end

  it 'maps the dashboard from live Snowflake' do
    allow(FinanceWarehouse::DashboardQueries).to receive(:enabled?).and_return(true)
    dashboard = FinanceWarehouse::DashboardQueries.new(client: @warehouse, as_of: ContractWarehouse::AS_OF).call
    expect(BigDecimal(dashboard[:collections_30_days]))
      .to eq(BigDecimal(parity.dig('must_agree', 'dashboard-summary', 'values', 'COLLECTIONS_30_DAYS')))
    expect(dashboard[:top_overdue_accounts].length).to eq(10)
  end

  it 'tags every statement and runs on the parity warehouse' do
    @warehouse.query(FinanceWarehouse::DashboardQueries::SUMMARY_SQL, binds) if @warehouse.query_ids.empty?
    ids = @warehouse.query_ids.dup
    expect(ids).not_to be_empty
    history = @warehouse.query(<<~SQL, [])
      SELECT QUERY_ID, QUERY_TAG, WAREHOUSE_NAME
      FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(RESULT_LIMIT => 1000))
      WHERE QUERY_ID IN (#{ids.map { |id| "'#{id.delete("'")}'" }.join(', ')})
    SQL
    expect(history.map { |row| row.fetch('QUERY_ID') }).to match_array(ids)
    history.each do |row|
      expect(row.fetch('QUERY_TAG')).to eq(ContractWarehouse::SnowflakeWarehouse::QUERY_TAG)
      expect(row.fetch('WAREHOUSE_NAME')).to eq(ContractWarehouse::SnowflakeWarehouse::WAREHOUSE)
    end
  end
end
