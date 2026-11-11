require 'rspec/core'
require 'json'
require 'bigdecimal'
require 'open3'
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
      query = QUERIES.fetch(sql)
      recorded = File.join(ROOT, 'recorded', 'teradata', "#{query}.json")
      target = ENV.fetch('WAREHOUSE_CONTRACT_TARGET', 'teradata-emulator')
      if target == 'replay'
        data = JSON.parse(File.read(recorded))
      else
        bridge = File.expand_path('../../../consumers/contract-kit/bridge.py', ROOT)
        command = [ENV.fetch('CONTRACT_KIT_PYTHON', 'python3'), bridge,
                   '--target', target, '--query', query]
        command += ['--record', recorded] if ENV['CONTRACT_RECORD'] == 'true'
        output, error, status = Open3.capture3(*command, stdin_data: sql)
        raise error unless status.success?

        data = JSON.parse(output)
      end
      data.fetch('rows').map { |row| data.fetch('columns').zip(row).to_h }
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
