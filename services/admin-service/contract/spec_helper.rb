require 'rspec/core'
require 'json'
require 'bigdecimal'
require_relative '../app/services/finance_warehouse/teradata_client'
require_relative '../app/services/finance_warehouse/dashboard_queries'

module ContractWarehouse
  ROOT = File.expand_path(__dir__).freeze
  QUERIES = {
    FinanceWarehouse::DashboardQueries::SUMMARY_SQL => 'dashboard-summary',
    FinanceWarehouse::DashboardQueries::OVERDUE_SQL => 'overdue-accounts'
  }.freeze

  class EmulatorWarehouse
    def query(sql)
      return execute_endpoint(ENV.fetch('TD_EMULATOR_URL'), sql) if ENV.key?('TD_EMULATOR_URL')

      data = JSON.parse(File.read(File.join(ROOT, 'recorded', 'teradata', "#{QUERIES.fetch(sql)}.json")))
      data.fetch('rows').map { |row| data.fetch('columns').zip(row).to_h }
    end

    private

    def execute_endpoint(_endpoint, _sql)
      raise NotImplementedError, 'emulator endpoint not configured'
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
