package com.bank.statements;

import java.math.BigDecimal;
import java.sql.Date;

public final class StatementLine {
    public final Date booked;
    public final String description;
    public final BigDecimal amount;
    public final BigDecimal balance;

    public StatementLine(Date booked, String description, BigDecimal amount, BigDecimal balance) {
        this.booked = booked;
        this.description = description;
        this.amount = amount;
        this.balance = balance;
    }
}
