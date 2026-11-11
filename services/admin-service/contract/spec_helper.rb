require 'rspec/core'
require 'json'
require 'bigdecimal'
require 'open3'
require_relative '../app/services/finance_warehouse/teradata_client'
require_relative '../app/services/finance_warehouse/databricks_client'
require_relative '../app/services/finance_warehouse/dashboard_queries'

module ContractWarehouse
  ROOT = File.expand_path(__dir__).freeze
  # Both paths pin CURRENT_DATE to the seeded business date so results are reproducible.
  AS_OF_DATE = ENV.fetch('CONTRACT_AS_OF_DATE', '2026-11-09').freeze
  NAMES = { summary: 'dashboard-summary', overdue: 'overdue-accounts' }.freeze
  SQL = FinanceWarehouse::DashboardQueries::SQL_BY_DIALECT
  QUERIES = SQL.fetch(:teradata).to_h { |key, sql| [sql, NAMES.fetch(key)] }.freeze
  DATABRICKS_QUERIES = SQL.fetch(:databricks).to_h { |key, sql| [sql, NAMES.fetch(key)] }.freeze
  DATABRICKS_KEYS = %w[DATABRICKS_HOST DATABRICKS_TOKEN DATABRICKS_WAREHOUSE_ID].freeze

  def self.pin(sql)
    raise ArgumentError, 'invalid CONTRACT_AS_OF_DATE' unless AS_OF_DATE.match?(/\A\d{4}-\d{2}-\d{2}\z/)

    sql.gsub(/\bCURRENT_DATE\b/, "DATE '#{AS_OF_DATE}'")
  end

  # Order-preserving, type-normalized rows so both paths compare value for value.
  def self.canonical(rows)
    rows.map do |row|
      row.transform_values do |value|
        text = value.to_s.rstrip
        text.match?(/\A-?\d+(\.\d+)?\z/) ? BigDecimal(text).to_s('F') : text
      end
    end
  end

  def self.databricks_configured?
    DATABRICKS_KEYS.none? { |key| ENV[key].to_s.empty? }
  end

  class EmulatorWarehouse
    def initialize(target: ENV.fetch('WAREHOUSE_CONTRACT_TARGET', 'teradata-emulator'))
      @target = target
    end

    def query(sql)
      query = QUERIES.fetch(sql)
      recorded = File.join(ROOT, 'recorded', 'teradata', "#{query}.json")
      if @target == 'replay'
        data = JSON.parse(File.read(recorded))
      else
        bridge = File.expand_path('../../../consumers/contract-kit/bridge.py', ROOT)
        command = [ENV.fetch('CONTRACT_KIT_PYTHON', 'python3'), bridge,
                   '--target', @target, '--query', query]
        command += ['--record', recorded] if ENV['CONTRACT_RECORD'] == 'true'
        output, error, status = Open3.capture3(*command, stdin_data: ContractWarehouse.pin(sql))
        raise error unless status.success?

        data = JSON.parse(output)
      end
      data.fetch('rows').map { |row| data.fetch('columns').zip(row).to_h }
    end
  end

  # Live target: runs the consumer's Databricks read logic against cpw.dbx_d1111_after.
  class DatabricksWarehouse < FinanceWarehouse::DatabricksClient
    def query(sql)
      run("/* contract query=#{DATABRICKS_QUERIES.fetch(sql)} as_of=#{AS_OF_DATE} */\n" + ContractWarehouse.pin(sql))
    end
  end

  class SnowflakeWarehouse
    DATABASE = 'SFX_D1110_AFTER'.freeze
    SCHEMA = 'COMPAT'.freeze
    QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"admin-service"}'.freeze

    def query(_sql)
      credentials = %w[ACCOUNT USER ROLE WAREHOUSE PRIVATE_KEY].map { |key| ENV["SNOWFLAKE_#{key}"] }
      raise ArgumentError, 'Snowflake environment not configured' if credentials.any? { |value| value.to_s.empty? }

      raise NotImplementedError,
            "Snowflake adapter not installed; execute supplied SQL in #{DATABASE}.#{SCHEMA} with QUERY_TAG=#{QUERY_TAG}"
    end
  end
end
