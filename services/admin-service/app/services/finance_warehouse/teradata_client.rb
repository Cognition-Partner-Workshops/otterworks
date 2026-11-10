module FinanceWarehouse
  class TeradataClient
    class Unavailable < StandardError; end

    def initialize(dsn: nil, connector: nil)
      @dsn = dsn || ENV.fetch('FINANCE_WAREHOUSE_DSN') do
        Rails.application.config_for(:finance_warehouse).fetch(:dsn)
      end
      @connector = connector
    end

    def query(sql)
      connection = connect
      statement = connection.run(sql)
      result = []
      while (row = statement.fetch_hash)
        result << row
      end
      result
    rescue LoadError, StandardError
      raise Unavailable, 'finance warehouse unavailable'
    ensure
      statement&.drop
      connection&.disconnect
    end

    private

    def connect
      return @connector.call(@dsn) if @connector

      require 'odbc'
      ODBC::Database.new.drvconnect(@dsn)
    end
  end
end
