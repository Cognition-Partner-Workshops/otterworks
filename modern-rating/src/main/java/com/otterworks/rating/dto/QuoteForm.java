package com.otterworks.rating.dto;

import com.otterworks.rating.model.Policy;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import java.math.BigDecimal;
import java.time.LocalDate;
import org.springframework.format.annotation.DateTimeFormat;

/** What the underwriter keys on the quote page; mirrors the legacy quote screen. */
public record QuoteForm(
        @NotNull @Pattern(regexp = "[A-Z]{2}") String line,
        @NotNull @Pattern(regexp = "[A-Z]{2}") String state,
        @NotNull @Pattern(regexp = "[0-9]{4,5}") String classCode,
        @NotNull @Pattern(regexp = "[0-9]{3}") String territory,
        @NotNull @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate effective,
        @NotNull @DecimalMin("0.00") BigDecimal exposure,
        @Min(0) @Max(99) int years,
        @Min(0) @Max(99) int claims,
        @Min(0) @Max(99999) int deductible,
        boolean multi,
        @Min(-99) @Max(99) int schedule,
        @Min(0) @Max(99) int addl,
        boolean equipment,
        boolean waiver,
        boolean hnoa) {

    public static QuoteForm example() {
        return new QuoteForm("GL", "IL", "91340", "001", LocalDate.of(2026, 3, 15),
                new BigDecimal("210.00"), 5, 0, 500, false, 0, 0, false, false, false);
    }

    public Policy toPolicy() {
        return new Policy("SCREEN", line, state, classCode, territory, effective, exposure, years, claims,
                deductible, multi, BigDecimal.valueOf(schedule, 2), addl, equipment, waiver, hnoa);
    }
}
