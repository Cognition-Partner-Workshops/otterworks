# Lakehouse parity

| Spec | Coverage IDs | NS | Business date | Legacy rows | Lakehouse rows | Result |
|---|---|---|---|---:|---:|---|
| [billing.account_hist_batch](parity/billing.account_hist_batch.json) | teradata_table:SFX_BILLING.ACCOUNT_HIST_BATCH, bteq_script:warehouse/teradata/scripts/billing/load_account_history.bteq | sfx-d1110-after | 20261109 | 1 | 1 | PASS |
| [billing.billing_adj](parity/billing.billing_adj.json) | teradata_table:SFX_BILLING.BILLING_ADJ, bteq_script:warehouse/teradata/scripts/billing/04_load_payments.bteq | sfx-d1110-after | 20261109 | 100 | 100 | PASS |
| [billing.credit_note](parity/billing.credit_note.json) | teradata_table:SFX_BILLING.CREDIT_NOTE, bteq_script:warehouse/teradata/scripts/billing/04_load_payments.bteq | sfx-d1110-after | 20261109 | 100 | 100 | PASS |
| [billing.customer_account](parity/billing.customer_account.json) | teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq | sfx-d1110-after | 20261109 | 300 | 300 | PASS |
| [billing.customer_account_hist](parity/billing.customer_account_hist.json) | teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT_HIST, bteq_script:warehouse/teradata/scripts/billing/load_account_history.bteq | sfx-d1110-after | 20261109 | 300 | 300 | PASS |
| [billing.gl_account](parity/billing.gl_account.json) | teradata_table:SFX_BILLING.GL_ACCOUNT, bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq | sfx-d1110-after | 20261109 | 10 | 10 | PASS |
| [billing.gl_journal_line](parity/billing.gl_journal_line.json) | teradata_table:SFX_BILLING.GL_JOURNAL_LINE, bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq | sfx-d1110-after | 20261109 | 830 | 830 | PASS |
| [billing.invoice_hdr](parity/billing.invoice_hdr.json) | teradata_table:SFX_BILLING.INVOICE_HDR, bteq_script:warehouse/teradata/scripts/billing/03_load_invoices.bteq | sfx-d1110-after | 20261109 | 2100 | 2100 | PASS |
| [billing.invoice_line](parity/billing.invoice_line.json) | teradata_table:SFX_BILLING.INVOICE_LINE, bteq_script:warehouse/teradata/scripts/billing/03_load_invoices.bteq | sfx-d1110-after | 20261109 | 2000 | 2000 | PASS |
| [billing.payment](parity/billing.payment.json) | teradata_table:SFX_BILLING.PAYMENT, bteq_script:warehouse/teradata/scripts/billing/04_load_payments.bteq | sfx-d1110-after | 20261109 | 2000 | 2000 | PASS |
| [billing.plan_catalog](parity/billing.plan_catalog.json) | teradata_table:SFX_BILLING.PLAN_CATALOG, bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq | sfx-d1110-after | 20261109 | 40 | 40 | PASS |
| [billing.stg_billing_adj](parity/billing.stg_billing_adj.json) | teradata_table:SFX_BILLING.STG_BILLING_ADJ | sfx-d1110-after | 20261109 | 100 | 100 | PASS |
| [billing.stg_credit_note](parity/billing.stg_credit_note.json) | teradata_table:SFX_BILLING.STG_CREDIT_NOTE | sfx-d1110-after | 20261109 | 100 | 100 | PASS |
| [billing.stg_customer_account](parity/billing.stg_customer_account.json) | teradata_table:SFX_BILLING.STG_CUSTOMER_ACCOUNT | sfx-d1110-after | 20261109 | 300 | 300 | PASS |
| [billing.stg_gl_account](parity/billing.stg_gl_account.json) | teradata_table:SFX_BILLING.STG_GL_ACCOUNT | sfx-d1110-after | 20261109 | 10 | 10 | PASS |
| [billing.stg_gl_journal_line](parity/billing.stg_gl_journal_line.json) | teradata_table:SFX_BILLING.STG_GL_JOURNAL_LINE | sfx-d1110-after | 20261109 | 830 | 830 | PASS |
| [billing.stg_invoice_hdr](parity/billing.stg_invoice_hdr.json) | teradata_table:SFX_BILLING.STG_INVOICE_HDR | sfx-d1110-after | 20261109 | 2100 | 2100 | PASS |
| [billing.stg_invoice_line](parity/billing.stg_invoice_line.json) | teradata_table:SFX_BILLING.STG_INVOICE_LINE | sfx-d1110-after | 20261109 | 2000 | 2000 | PASS |
| [billing.stg_payment](parity/billing.stg_payment.json) | teradata_table:SFX_BILLING.STG_PAYMENT | sfx-d1110-after | 20261109 | 2000 | 2000 | PASS |
| [billing.stg_plan_catalog](parity/billing.stg_plan_catalog.json) | teradata_table:SFX_BILLING.STG_PLAN_CATALOG | sfx-d1110-after | 20261109 | 40 | 40 | PASS |
| [billing.stg_subscription](parity/billing.stg_subscription.json) | teradata_table:SFX_BILLING.STG_SUBSCRIPTION | sfx-d1110-after | 20261109 | 500 | 500 | PASS |
| [billing.stg_tax_rate](parity/billing.stg_tax_rate.json) | teradata_table:SFX_BILLING.STG_TAX_RATE | sfx-d1110-after | 20261109 | 200 | 200 | PASS |
| [billing.stg_usage_daily](parity/billing.stg_usage_daily.json) | teradata_table:SFX_BILLING.STG_USAGE_DAILY | sfx-d1110-after | 20261109 | 2000 | 2000 | PASS |
| [billing.subscription](parity/billing.subscription.json) | teradata_table:SFX_BILLING.SUBSCRIPTION, bteq_script:warehouse/teradata/scripts/billing/02_load_subscriptions.bteq | sfx-d1110-after | 20261109 | 500 | 500 | PASS |
| [billing.tax_rate](parity/billing.tax_rate.json) | teradata_table:SFX_BILLING.TAX_RATE, bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq | sfx-d1110-after | 20261109 | 200 | 200 | PASS |
| [billing.usage_daily](parity/billing.usage_daily.json) | teradata_table:SFX_BILLING.USAGE_DAILY, bteq_script:warehouse/teradata/scripts/billing/05_load_usage.bteq | sfx-d1110-after | 20261109 | 2000 | 2000 | PASS |
