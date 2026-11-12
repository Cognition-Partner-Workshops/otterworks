package app.synthetic.insurance.iri.values;

import java.math.BigDecimal;
import java.time.LocalDate;

/** One POLICY_VALUES row, read with exact decimals (no binary floating point). */
record PolicyValuesRow(long contractNo, LocalDate valuationDate, BigDecimal accountValue,
                       BigDecimal surrenderValue, BigDecimal cashValue, BigDecimal premiumsToDate,
                       BigDecimal withdrawalsToDate, BigDecimal deathBenefit, BigDecimal surrenderCharge) {}
