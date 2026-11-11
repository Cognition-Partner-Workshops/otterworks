require 'json'
require 'open3'
require 'bigdecimal'
require_relative 'teradata_client'

module FinanceWarehouse
  # Uses the shared Python SQL connector without changing the Teradata client.
  class DatabricksClient
    def initialize(python: ENV.fetch('CONTRACT_KIT_PYTHON', 'python3'))
      @python = python
    end

    def query(sql, parameters = [])
      run(sql, parameters)
    rescue StandardError
      raise TeradataClient::Unavailable, 'finance warehouse unavailable'
    end

    def run(sql, parameters = [])
      bridge = File.expand_path('../../../../../consumers/contract-kit/databricks_bridge.py', __dir__)
      output, error, status = Open3.capture3(@python, bridge, 'admin-service',
                                             stdin_data: JSON.generate(sql: sql, parameters: parameters))
      raise "Databricks query failed: #{error}" unless status.success?

      result = JSON.parse(output)
      result.fetch('rows').map do |row|
        result.fetch('columns').zip(row).to_h
      end
    end
  end
end
