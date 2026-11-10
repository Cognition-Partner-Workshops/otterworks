package com.otterworks.report.financewarehouse;

import java.math.BigDecimal;

public class UnreconciledInvoice {
    public final String invoiceNo;
    public final String accountNo;
    public final String invoiceDate;
    public final int daysOverdue;
    public final BigDecimal amountDue;
    public final BigDecimal paid;

    public UnreconciledInvoice(String invoiceNo, String accountNo, String invoiceDate,
                              int daysOverdue, BigDecimal amountDue, BigDecimal paid) {
        this.invoiceNo = invoiceNo;
        this.accountNo = accountNo;
        this.invoiceDate = invoiceDate;
        this.daysOverdue = daysOverdue;
        this.amountDue = amountDue;
        this.paid = paid;
    }
}
