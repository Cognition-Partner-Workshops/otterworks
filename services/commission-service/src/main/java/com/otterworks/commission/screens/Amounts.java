package com.otterworks.commission.screens;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.util.List;
import java.util.Locale;

/**
 * Display of stored amounts and percentages. Values are shown as stored at
 * scale 2; formatting never rounds (RoundingMode.UNNECESSARY fails instead).
 */
public final class Amounts {

    private Amounts() {
    }

    public static String format(BigDecimal value) {
        if (value == null) {
            return "";
        }
        DecimalFormat f = new DecimalFormat("#,##0.00", DecimalFormatSymbols.getInstance(Locale.ROOT));
        f.setRoundingMode(RoundingMode.UNNECESSARY);
        return f.format(value.setScale(2, RoundingMode.UNNECESSARY));
    }

    /** Sum of the row amounts: BigDecimal addition is exact, so no rounding mode applies. */
    public static BigDecimal total(List<ScreensRepository.StatementRow> rows) {
        return rows.stream().map(ScreensRepository.StatementRow::commission)
                .reduce(BigDecimal.ZERO.setScale(2), BigDecimal::add);
    }
}
