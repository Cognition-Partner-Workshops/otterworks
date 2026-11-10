package com.otterworks.report.financewarehouse;

import java.math.BigDecimal;
import java.util.Collections;
import java.util.List;

public class FinanceReconciliation {
    public final int period;
    public final BigDecimal invoicedTotal;
    public final BigDecimal paidTotal;
    public final BigDecimal arGlBalance;
    public final BigDecimal variance;
    public final List<UnreconciledInvoice> unreconciledInvoices;

    public FinanceReconciliation(int period, BigDecimal invoicedTotal, BigDecimal paidTotal,
                                 BigDecimal arGlBalance) {
        this(period, invoicedTotal, paidTotal, arGlBalance, Collections.emptyList());
    }

    public FinanceReconciliation(int period, BigDecimal invoicedTotal, BigDecimal paidTotal,
                                 BigDecimal arGlBalance, List<UnreconciledInvoice> unreconciledInvoices) {
        this.period = period;
        this.invoicedTotal = invoicedTotal;
        this.paidTotal = paidTotal;
        this.arGlBalance = arGlBalance;
        this.variance = invoicedTotal.subtract(paidTotal).subtract(arGlBalance);
        this.unreconciledInvoices = unreconciledInvoices;
    }
}
