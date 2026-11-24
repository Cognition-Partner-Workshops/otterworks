package com.otterworks.rating.model;

import java.math.BigDecimal;

/**
 * One rated policy.
 *
 * @param status OK, DEC (declined) or REJ (rejected)
 * @param factorSource T territory row, D default territory, O override
 */
public record Quote(
        String policyId,
        String status,
        String reason,
        BigDecimal basePremium,
        BigDecimal modifiedPremium,
        boolean minimumApplied,
        BigDecimal endorsements,
        BigDecimal fee,
        BigDecimal total,
        String factorSource) {

    public static Quote refused(String policyId, String status, String reason) {
        return new Quote(policyId, status, reason, BigDecimal.ZERO, BigDecimal.ZERO, false,
                BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO, "");
    }

    /** Canonical pipe-delimited line, amounts in cents, shared with the parity driver. */
    public String asLine() {
        return String.join("|", policyId, status, reason, cents(basePremium), cents(modifiedPremium),
                minimumApplied ? "Y" : "N", cents(endorsements), cents(fee), cents(total), factorSource);
    }

    private static String cents(BigDecimal amount) {
        return amount.movePointRight(2).setScale(0, java.math.RoundingMode.UNNECESSARY).toPlainString();
    }
}
