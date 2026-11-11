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

  it 'matches the 200k shared-seed emulator summary within tolerance', :aggregate_failures do
    rows = @warehouse.query(FinanceWarehouse::DashboardQueries::SUMMARY_SQL, binds)
    puts "Live dashboard summary: #{JSON.generate(rows)}"
    expected = parity.dig('must_agree', 'dashboard-summary')
    expect(rows.length).to eq(expected.fetch('row_count'))
    expect(rows.first.keys).to eq(recorded('dashboard-summary').fetch('columns'))
    expected.fetch('values').each do |column, value|
      tolerance = BigDecimal(expected.fetch('tolerances').fetch(column))
      expect(BigDecimal(rows.first.fetch(column))).to be_within(tolerance).of(BigDecimal(value)),
        "#{column} differs from the 200k emulator: target data gap, merge blocked"
    end
  end

  it 'matches billed and credits inputs from the same 200k seed', :aggregate_failures do
    rows = @warehouse.query(<<~SQL, binds)
      WITH #{FinanceWarehouse::DashboardQueries::AS_OF}, invoices AS (
        SELECT ZEROIFNULL(SUM(CASE
          WHEN i.INVOICE_DATE > DATEADD(day, -30, params.AS_OF) AND i.INVOICE_DATE <= params.AS_OF
            AND i.INVOICE_DATE >= DATE '2020-01-01' THEN i.TOTAL_AMOUNT ELSE 0 END)) AS BILLED_30_DAYS,
          COUNT(*) AS INVOICE_ROWS,
          SUM(i.TOTAL_AMOUNT) AS TOTAL_AMOUNT
        FROM COMPAT.INVOICE_HDR i CROSS JOIN params
      ), credits AS (
        SELECT ZEROIFNULL(SUM(c.AMOUNT)) AS CREDITS_30_DAYS
        FROM CORE_BILLING.STG_BILLING__CREDIT_NOTE c CROSS JOIN params
        WHERE c.CREDIT_DT > DATEADD(day, -30, params.AS_OF) AND c.CREDIT_DT <= params.AS_OF
      )
      SELECT invoices.*, credits.CREDITS_30_DAYS FROM invoices CROSS JOIN credits
    SQL
    puts "Live billing inputs: #{JSON.generate(rows)}"
    expected = parity.dig('must_agree', 'billing-inputs')
    expected.fetch('values').each do |column, value|
      expect(BigDecimal(rows.first.fetch(column)))
        .to be_within(BigDecimal(expected.fetch('tolerance'))).of(BigDecimal(value)),
            "#{column} differs from the 200k emulator: target data gap, merge blocked"
    end
  end

  it 'returns the same top overdue accounts, due dates and balances as the 200k emulator', :aggregate_failures do
    rows = @warehouse.query(FinanceWarehouse::DashboardQueries::OVERDUE_SQL, binds)
    expected = parity.dig('must_agree', 'overdue-accounts')
    tolerance = BigDecimal(expected.fetch('tolerance'))
    puts "Live overdue accounts: #{JSON.generate(rows.map { |row| row.except('CUSTOMER_NAME') })}"
    expect(rows.length).to eq(expected.fetch('row_count'))
    expect(rows.first.keys).to eq(recorded('overdue-accounts').fetch('columns'))
    expect(rows.map { |row| row.fetch('ACCOUNT_NO') })
      .to eq(expected.fetch('rows').map { |row| row.fetch('ACCOUNT_NO') }),
          'top-10 membership or order differs from the 200k emulator: target data gap, merge blocked'
    rows.zip(expected.fetch('rows')).each do |row, reference|
      account = reference.fetch('ACCOUNT_NO')
      expect(row.fetch('OLDEST_DUE_DATE')).to eq(reference.fetch('OLDEST_DUE_DATE')), "#{account} oldest due date"
      expect(BigDecimal(row.fetch('OVERDUE_BALANCE')))
        .to be_within(tolerance).of(BigDecimal(reference.fetch('OVERDUE_BALANCE'))), "#{account} overdue balance"
    end
  end

  it 'maps the dashboard from live Snowflake' do
    allow(FinanceWarehouse::DashboardQueries).to receive(:enabled?).and_return(true)
    dashboard = FinanceWarehouse::DashboardQueries.new(client: @warehouse, as_of: ContractWarehouse::AS_OF).call
    summary = parity.dig('must_agree', 'dashboard-summary', 'values')
    expect(BigDecimal(dashboard[:collections_30_days])).to eq(BigDecimal(summary.fetch('COLLECTIONS_30_DAYS')))
    expect(BigDecimal(dashboard[:ar_open_balance])).to eq(BigDecimal(summary.fetch('AR_OPEN_BALANCE')))
    expect(BigDecimal(dashboard[:dso])).to be_within(BigDecimal('0.0001')).of(BigDecimal(summary.fetch('DSO')))
    expect(dashboard[:top_overdue_accounts].map { |account| account[:account_no] })
      .to eq(parity.dig('must_agree', 'overdue-accounts', 'rows').map { |row| row.fetch('ACCOUNT_NO') })
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
