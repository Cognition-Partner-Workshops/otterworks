require_relative 'spec_helper'

RSpec.describe FinanceWarehouse::DashboardQueries do
  let(:client) do
    case ENV.fetch('WAREHOUSE_CONTRACT_TARGET', 'teradata-emulator')
    when 'teradata-emulator', 'replay', 'snowflake-semantics'
      ContractWarehouse::EmulatorWarehouse.new
    when 'databricks'
      skip 'Databricks environment not configured (DATABRICKS_HOST/TOKEN/WAREHOUSE_ID)' unless ContractWarehouse.databricks_configured?
      ContractWarehouse::DatabricksWarehouse.new
    when 'snowflake'
      keys = %w[ACCOUNT USER ROLE WAREHOUSE PRIVATE_KEY]
      skip 'Snowflake environment not configured' if keys.any? { |key| ENV["SNOWFLAKE_#{key}"].to_s.empty? }
      ContractWarehouse::SnowflakeWarehouse.new
    else
      raise ArgumentError, 'unknown WAREHOUSE_CONTRACT_TARGET'
    end
  end

  target = ENV.fetch('WAREHOUSE_CONTRACT_TARGET', 'teradata-emulator')
  queries = target == 'databricks' ? ContractWarehouse::DATABRICKS_QUERIES : ContractWarehouse::QUERIES

  queries.each do |sql, query|
    it "matches #{query} row count and aggregates" do
      expected = JSON.parse(File.read(File.join(ContractWarehouse::ROOT, 'expected', "#{query}.json")))
      rows = client.query(sql)
      expect(rows.length).to eq(expected.fetch('row_count'))
      expected.fetch('sums').each do |column, sum|
        expect(rows.sum { |row| BigDecimal(row.fetch(column).to_s) }).to eq(BigDecimal(sum))
      end
      expect(rows.map { |row| row.fetch('ACCOUNT_NO') }).to eq(expected['keys']) if expected.key?('keys')
    end
  end

  it 'maps the dashboard using the selected warehouse' do
    allow(described_class).to receive(:enabled?).and_return(true)
    dashboard = described_class.new(client: client).call
    expected = JSON.parse(File.read(File.join(ContractWarehouse::ROOT, 'expected', 'dashboard-summary.json')))
    accounts = JSON.parse(File.read(File.join(ContractWarehouse::ROOT, 'expected', 'overdue-accounts.json')))
    expect(BigDecimal(dashboard[:ar_open_balance])).to eq(BigDecimal(expected.fetch('sums').fetch('AR_OPEN_BALANCE')))
    expect(dashboard[:top_overdue_accounts].length).to eq(accounts.fetch('row_count'))
  end

  if target == 'databricks'
    ContractWarehouse::NAMES.each do |key, query|
      it "returns the same #{query} rows as the Teradata emulator old path" do
        skip 'Teradata emulator not configured (TD_PG_PORT)' if ENV['TD_PG_PORT'].to_s.empty?
        old_path = ContractWarehouse::EmulatorWarehouse.new(target: 'teradata-emulator')
                                                    .query(ContractWarehouse::SQL.fetch(:teradata).fetch(key))
        new_path = client.query(ContractWarehouse::SQL.fetch(:databricks).fetch(key))
        expect(ContractWarehouse.canonical(new_path)).to eq(ContractWarehouse.canonical(old_path))
      end
    end
  end
end
