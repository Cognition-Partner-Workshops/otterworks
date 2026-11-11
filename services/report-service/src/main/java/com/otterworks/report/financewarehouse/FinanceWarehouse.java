package com.otterworks.report.financewarehouse;

public interface FinanceWarehouse {
    FinanceReconciliation reconcile(int period);
}
