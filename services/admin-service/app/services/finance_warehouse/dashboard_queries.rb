require 'bigdecimal'

module FinanceWarehouse
  class DashboardQueries
    class Disabled < StandardError; end

    CACHE_KEY = 'finance_warehouse/dashboard'.freeze
    AS_OF = <<~SQL.chomp.freeze
      params AS (SELECT COALESCE(TRY_TO_DATE(?), CURRENT_DATE) AS AS_OF)
    SQL
    SUMMARY_SQL = <<~SQL.freeze
      WITH #{AS_OF}, ar AS (
        SELECT ZEROIFNULL(SUM(j.DEBIT_AMOUNT - j.CREDIT_AMOUNT)) AS AR_OPEN_BALANCE
        FROM COMPAT.GL_JOURNAL_LINE j
        JOIN COMPAT.GL_ACCOUNT a ON a.GL_ACCOUNT_ID = j.GL_ACCOUNT_ID
        WHERE UPPER(RTRIM(a.ACCOUNT_NUMBER)) = '1200'
      ), billed AS (
        SELECT ZEROIFNULL(SUM(i.TOTAL_AMOUNT)) AS BILLED_30_DAYS
        FROM COMPAT.INVOICE_HDR i CROSS JOIN params
        WHERE i.INVOICE_DATE > DATEADD(day, -30, params.AS_OF) AND i.INVOICE_DATE <= params.AS_OF
          AND i.INVOICE_DATE >= DATE '2020-01-01'
      ), credits AS (
        SELECT ZEROIFNULL(SUM(c.AMOUNT)) AS CREDITS_30_DAYS
        FROM CORE_BILLING.STG_BILLING__CREDIT_NOTE c CROSS JOIN params
        WHERE c.CREDIT_DT > DATEADD(day, -30, params.AS_OF) AND c.CREDIT_DT <= params.AS_OF
      ), collected AS (
        SELECT ZEROIFNULL(SUM(p.AMOUNT)) AS COLLECTIONS_30_DAYS
        FROM COMPAT.PAYMENT p CROSS JOIN params
        WHERE p.PAYMENT_DATE > DATEADD(day, -30, params.AS_OF) AND p.PAYMENT_DATE <= params.AS_OF
      ), net_billed AS (
        SELECT billed.BILLED_30_DAYS - credits.CREDITS_30_DAYS AS AMOUNT
        FROM billed CROSS JOIN credits
      ), metrics AS (
        SELECT ar.AR_OPEN_BALANCE, collected.COLLECTIONS_30_DAYS,
          ar.AR_OPEN_BALANCE * 30 / NULLIFZERO(net_billed.AMOUNT) AS RAW_DSO
        FROM ar CROSS JOIN net_billed CROSS JOIN collected
      )
      SELECT AR_OPEN_BALANCE, COLLECTIONS_30_DAYS, ZEROIFNULL(RAW_DSO) AS DSO FROM metrics
    SQL
    OVERDUE_SQL = <<~SQL.freeze
      WITH #{AS_OF}, paid AS (
        SELECT INVOICE_HDR_ID, SUM(AMOUNT) AS PAID FROM COMPAT.PAYMENT GROUP BY INVOICE_HDR_ID
      ), overdue AS (
        SELECT i.CUSTOMER_ID, DATEADD(day, 30, i.INVOICE_DATE) AS DUE_DT,
          i.TOTAL_AMOUNT - ZEROIFNULL(p.PAID) AS OPEN_BALANCE
        FROM COMPAT.INVOICE_HDR i
        CROSS JOIN params
        LEFT JOIN paid p ON p.INVOICE_HDR_ID = i.INVOICE_HDR_ID
        WHERE i.INVOICE_DATE >= DATE '2020-01-01' AND DATEADD(day, 30, i.INVOICE_DATE) < params.AS_OF
          AND i.TOTAL_AMOUNT - ZEROIFNULL(p.PAID) > 0
      ), accounts AS (
        SELECT a.ACCOUNT_NUMBER AS ACCOUNT_NO, a.ACCOUNT_NAME AS CUSTOMER_NAME,
          TO_CHAR(MIN(o.DUE_DT), 'YYYY-MM-DD') AS OLDEST_DUE_DATE,
          SUM(o.OPEN_BALANCE) AS OVERDUE_BALANCE
        FROM overdue o JOIN COMPAT.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = o.CUSTOMER_ID
        GROUP BY a.ACCOUNT_NUMBER, a.ACCOUNT_NAME
      )
      SELECT ACCOUNT_NO, CUSTOMER_NAME, OLDEST_DUE_DATE, OVERDUE_BALANCE FROM accounts
      ORDER BY OVERDUE_BALANCE DESC, UPPER(ACCOUNT_NO), ACCOUNT_NO
      LIMIT 10
    SQL

    def self.enabled?
      ActiveModel::Type::Boolean.new.cast(Rails.application.config_for(:finance_warehouse).fetch(:enabled))
    end

    def initialize(client: SnowflakeClient.new, as_of: nil)
      @client = client
      @as_of = as_of
    end

    def dashboard
      check_enabled!
      Rails.cache.fetch(cache_key, expires_in: 1.hour) { call }
    end

    def refresh
      result = call
      Rails.cache.write(cache_key, result, expires_in: 1.hour)
      result
    end

    def call
      check_enabled!
      summary = @client.query(SUMMARY_SQL, binds).fetch(0)
      {
        dso: decimal(summary.fetch('DSO')),
        ar_open_balance: decimal(summary.fetch('AR_OPEN_BALANCE')),
        collections_30_days: decimal(summary.fetch('COLLECTIONS_30_DAYS')),
        top_overdue_accounts: @client.query(OVERDUE_SQL, binds).map { |row| overdue_account(row) }
      }
    end

    private

    def cache_key
      @as_of ? "#{CACHE_KEY}/#{@as_of.iso8601}" : CACHE_KEY
    end

    def binds
      [@as_of&.iso8601.to_s]
    end

    def check_enabled!
      raise Disabled, 'finance warehouse is disabled' unless self.class.enabled?
    end

    def decimal(value)
      BigDecimal(value.to_s).to_s('F')
    end

    def overdue_account(row)
      {
        account_no: row.fetch('ACCOUNT_NO').to_s.strip,
        customer_name: row.fetch('CUSTOMER_NAME'),
        oldest_due_date: row.fetch('OLDEST_DUE_DATE').to_s,
        overdue_balance: decimal(row.fetch('OVERDUE_BALANCE'))
      }
    end
  end
end
