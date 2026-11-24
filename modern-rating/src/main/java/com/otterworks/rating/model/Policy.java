package com.otterworks.rating.model;

import java.math.BigDecimal;
import java.time.LocalDate;

public record Policy(
        String id,
        String line,
        String state,
        String classCode,
        String territory,
        LocalDate effective,
        BigDecimal exposure,
        int yearsInBusiness,
        int claims,
        int deductible,
        boolean multiPolicy,
        BigDecimal scheduleMod,
        int additionalInsureds,
        boolean equipment,
        boolean waiver,
        boolean hiredNonOwned) {}
