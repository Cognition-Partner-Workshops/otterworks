require 'bigdecimal'

module FinanceWarehouse
  class DashboardQueries
    class Disabled < StandardError; end

    CACHE_KEY = 'finance_warehouse/dashboard'.freeze
    SUMMARY_SQL = <<~SQL.freeze
      WITH ar AS (
        SEL ZEROIFNULL(SUM(j.DEBIT_AMOUNT - j.CREDIT_AMOUNT)) AS AR_OPEN_BALANCE
        FROM SFX_BILLING.GL_JOURNAL_LINE j
        JOIN SFX_BILLING.GL_ACCOUNT a ON a.GL_ACCOUNT_ID = j.GL_ACCOUNT_ID
        WHERE a.ACCOUNT_NUMBER = '1200'
      ), billed AS (
        SEL ZEROIFNULL(SUM(TOTAL_AMOUNT)) AS BILLED_30_DAYS FROM SFX_BILLING.INVOICE_HDR
        WHERE INVOICE_DT > CURRENT_DATE - 30 AND INVOICE_DT <= CURRENT_DATE
          AND INVOICE_DT >= 1200101
      ), credits AS (
        SEL ZEROIFNULL(SUM(AMOUNT)) AS CREDITS_30_DAYS FROM SFX_BILLING.CREDIT_NOTE
        WHERE CREDIT_DT > CURRENT_DATE - 30 AND CREDIT_DT <= CURRENT_DATE
      ), collected AS (
        SEL ZEROIFNULL(SUM(AMOUNT)) AS COLLECTIONS_30_DAYS FROM SFX_BILLING.PAYMENT
        WHERE PAYMENT_DT > CURRENT_DATE - 30 AND PAYMENT_DT <= CURRENT_DATE
      ), net_billed AS (
        SEL billed.BILLED_30_DAYS - credits.CREDITS_30_DAYS AS AMOUNT
        FROM billed CROSS JOIN credits
      ), metrics AS (
        SEL ar.AR_OPEN_BALANCE, collected.COLLECTIONS_30_DAYS,
          ar.AR_OPEN_BALANCE / NULLIFZERO(net_billed.AMOUNT) * 30 AS RAW_DSO
        FROM ar CROSS JOIN net_billed CROSS JOIN collected
      )
      SEL AR_OPEN_BALANCE, COLLECTIONS_30_DAYS, ZEROIFNULL(RAW_DSO) AS DSO FROM metrics
    SQL
    OVERDUE_SQL = <<~SQL.freeze
      WITH overdue AS (
        SEL i.CUSTOMER_ID, i.INVOICE_DT + 30 AS DUE_DT, i.TOTAL_AMOUNT - ZEROIFNULL(p.PAID) AS OPEN_BALANCE
        FROM SFX_BILLING.INVOICE_HDR i
        LEFT JOIN (
          SEL INVOICE_ID, SUM(AMOUNT) AS PAID FROM SFX_BILLING.PAYMENT GROUP BY INVOICE_ID
        ) p ON p.INVOICE_ID = i.INVOICE_ID
        WHERE i.INVOICE_DT >= 1200101 AND (i.INVOICE_DT + 30) < CURRENT_DATE
          AND i.TOTAL_AMOUNT - ZEROIFNULL(p.PAID) > 0
      ), accounts AS (
        SEL a.ACCOUNT_NUMBER AS ACCOUNT_NO, a.ACCOUNT_NAME AS CUSTOMER_NAME,
          CAST(MIN(i.DUE_DT) AS DATE FORMAT 'YYYY-MM-DD') AS OLDEST_DUE_DATE,
          SUM(i.OPEN_BALANCE) AS OVERDUE_BALANCE
        FROM overdue i JOIN SFX_BILLING.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = i.CUSTOMER_ID
        GROUP BY a.ACCOUNT_NUMBER, a.ACCOUNT_NAME
      )
      SEL TOP 10 ACCOUNT_NO, CUSTOMER_NAME, OLDEST_DUE_DATE, OVERDUE_BALANCE FROM accounts
      QUALIFY ROW_NUMBER() OVER (ORDER BY OVERDUE_BALANCE DESC, ACCOUNT_NO) <= 10
      ORDER BY OVERDUE_BALANCE DESC, ACCOUNT_NO
    SQL

    def self.enabled?
      ActiveModel::Type::Boolean.new.cast(Rails.application.config_for(:finance_warehouse).fetch(:enabled))
    end

    def initialize(client: TeradataClient.new)
      @client = client
    end

    def dashboard
      check_enabled!
      Rails.cache.fetch(CACHE_KEY, expires_in: 1.hour) { call }
    end

    def refresh
      result = call
      Rails.cache.write(CACHE_KEY, result, expires_in: 1.hour)
      result
    end

    def call
      check_enabled!
      summary = @client.query(SUMMARY_SQL).fetch(0)
      {
        dso: decimal(summary.fetch('DSO')),
        ar_open_balance: decimal(summary.fetch('AR_OPEN_BALANCE')),
        collections_30_days: decimal(summary.fetch('COLLECTIONS_30_DAYS')),
        top_overdue_accounts: @client.query(OVERDUE_SQL).map { |row| overdue_account(row) }
      }
    end

    private

    def check_enabled!
      raise Disabled, 'finance warehouse is disabled' unless self.class.enabled?
    end

    def decimal(value)
      BigDecimal(value.to_s).to_s('F')
    end

    def overdue_account(row)
      {
        account_no: row.fetch('ACCOUNT_NO').strip,
        customer_name: row.fetch('CUSTOMER_NAME'),
        oldest_due_date: row.fetch('OLDEST_DUE_DATE').to_s,
        overdue_balance: decimal(row.fetch('OVERDUE_BALANCE'))
      }
    end
  end
end
