require 'bigdecimal'

module FinanceWarehouse
  class DashboardQueries
    class Disabled < StandardError; end

    CACHE_KEY = 'finance_warehouse/dashboard'.freeze
    SUMMARY_SQL = <<~SQL.freeze
      WITH balances AS (
        SEL i.AMOUNT_DUE - ZEROIFNULL(p.PAID) AS OPEN_BALANCE
        FROM FIN_DW.INVOICE i
        LEFT JOIN (
          SEL INVOICE_ID, SUM(AMOUNT) AS PAID FROM FIN_DW.PAYMENT GROUP BY INVOICE_ID
        ) p ON p.INVOICE_ID = i.INVOICE_ID
        WHERE i.INVOICE_DT >= 1200101
      ), ar AS (
        SEL ZEROIFNULL(SUM(CASE WHEN OPEN_BALANCE > 0 THEN OPEN_BALANCE ELSE 0 END)) AS AR_OPEN_BALANCE
        FROM balances
      ), billed AS (
        SEL ZEROIFNULL(SUM(AMOUNT_DUE)) AS BILLED_30_DAYS FROM FIN_DW.INVOICE
        WHERE INVOICE_DT > CURRENT_DATE - 30 AND INVOICE_DT <= CURRENT_DATE
      ), collected AS (
        SEL ZEROIFNULL(SUM(AMOUNT)) AS COLLECTIONS_30_DAYS FROM FIN_DW.PAYMENT
        WHERE PAYMENT_DT > CURRENT_DATE - 30 AND PAYMENT_DT <= CURRENT_DATE
      )
      SEL ar.AR_OPEN_BALANCE, collected.COLLECTIONS_30_DAYS,
        ZEROIFNULL(ar.AR_OPEN_BALANCE / NULLIFZERO(billed.BILLED_30_DAYS) * 30) AS DSO
      FROM ar CROSS JOIN billed CROSS JOIN collected
    SQL
    OVERDUE_SQL = <<~SQL.freeze
      WITH overdue AS (
        SEL i.ACCOUNT_ID, i.DUE_DT, i.AMOUNT_DUE - ZEROIFNULL(p.PAID) AS OPEN_BALANCE
        FROM FIN_DW.INVOICE i
        LEFT JOIN (
          SEL INVOICE_ID, SUM(AMOUNT) AS PAID FROM FIN_DW.PAYMENT GROUP BY INVOICE_ID
        ) p ON p.INVOICE_ID = i.INVOICE_ID
        WHERE i.INVOICE_DT >= 1200101 AND i.DUE_DT < CURRENT_DATE
          AND i.AMOUNT_DUE - ZEROIFNULL(p.PAID) > 0
      )
      SEL TOP 10 a.ACCOUNT_NO, c.CUSTOMER_NAME,
        CAST(MIN(i.DUE_DT) AS DATE FORMAT 'YYYY-MM-DD') AS OLDEST_DUE_DATE,
        SUM(i.OPEN_BALANCE) AS OVERDUE_BALANCE
      FROM overdue i JOIN FIN_DW.ACCOUNT a ON a.ACCOUNT_ID = i.ACCOUNT_ID
      JOIN FIN_DW.CUSTOMER c ON c.CUSTOMER_ID = a.CUSTOMER_ID
      GROUP BY a.ACCOUNT_NO, c.CUSTOMER_NAME
      QUALIFY ROW_NUMBER() OVER (ORDER BY SUM(i.OPEN_BALANCE) DESC, a.ACCOUNT_NO) <= 10
      ORDER BY OVERDUE_BALANCE DESC, a.ACCOUNT_NO
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
