require 'rspec/core'
require 'json'
require 'bigdecimal'
require 'date'
require 'open3'
require_relative '../app/services/finance_warehouse/snowflake_client'
require_relative '../app/services/finance_warehouse/dashboard_queries'

module ContractWarehouse
  ROOT = File.expand_path(__dir__).freeze
  QUERIES = {
    FinanceWarehouse::DashboardQueries::SUMMARY_SQL => 'dashboard-summary',
    FinanceWarehouse::DashboardQueries::OVERDUE_SQL => 'overdue-accounts'
  }.freeze
  # Business date the replay fixtures and the parity emulator load were produced for.
  AS_OF = Date.new(2026, 11, 9)

  # Replays recorded Teradata results, or sends the frozen legacy Teradata SQL in
  # contract/legacy/ to the contract-kit emulator bridge for parity runs.
  class EmulatorWarehouse
    def query(sql, _binds = [])
      query = QUERIES.find { |statement, _name| statement == sql }&.last
      raise KeyError, 'Unknown contract SQL' unless query
      recorded = File.join(ROOT, 'recorded', 'teradata', "#{query}.json")
      target = ENV.fetch('WAREHOUSE_CONTRACT_TARGET', 'teradata-emulator')
      if target == 'replay'
        data = JSON.parse(File.read(recorded))
      else
        unless %w[teradata-emulator snowflake-semantics].include?(target)
          raise ArgumentError, 'Unsupported bridge target'
        end
        bridge = File.expand_path('../../../consumers/contract-kit/bridge.py', ROOT)
        python = ENV.fetch('CONTRACT_KIT_PYTHON', 'python3')
        unless python.match?(%r{\A[A-Za-z0-9_./ -]+\z}) &&
               File.basename(python).match?(/\Apython(?:[0-9]+(?:\.[0-9]+)*)?\z/)
          raise ArgumentError, 'Invalid Python executable path'
        end
        if python.include?('/') && !(File.file?(python) && File.executable?(python))
          raise ArgumentError, 'Python path must name an executable file'
        end
        command = [[python, python], bridge,
                   '--target', target, '--query', query]
        command += ['--record', recorded] if ENV['CONTRACT_RECORD'] == 'true'
        legacy_sql = File.read(File.join(ROOT, 'legacy', "#{query}.sql"))
        output, error, status = Open3.capture3(*command, stdin_data: legacy_sql)
        raise error unless status.success?

        data = JSON.parse(output)
      end
      data.fetch('rows').map { |row| data.fetch('columns').zip(row).to_h }
    end
  end

  # Runs the production SQL against live Snowflake through the production client.
  class SnowflakeWarehouse
    DATABASE = 'SFX_D1110_AFTER'.freeze
    SCHEMA = 'COMPAT'.freeze
    WAREHOUSE = 'SFX_D1110_PARITY_WH'.freeze
    QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"admin-service"}'.freeze
    CREDENTIALS = %w[SNOWFLAKE_ACCOUNT SNOWFLAKE_USER SNOWFLAKE_ROLE SNOWFLAKE_PRIVATE_KEY].freeze

    def self.configured?
      CREDENTIALS.none? { |key| ENV[key].to_s.empty? }
    end

    def initialize
      @client = FinanceWarehouse::SnowflakeClient.new(
        database: DATABASE, schema: SCHEMA, warehouse: WAREHOUSE, query_tag: QUERY_TAG
      )
    end

    def query(sql, binds = [])
      @client.query(sql, binds)
    end

    def query_ids
      @client.query_ids
    end
  end
end
