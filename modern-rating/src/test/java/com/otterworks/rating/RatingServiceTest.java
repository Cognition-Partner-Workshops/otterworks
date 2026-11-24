package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.config.RatingProperties;
import com.otterworks.rating.model.PolicyRecordReader;
import com.otterworks.rating.model.Quote;
import com.otterworks.rating.service.RatingService;
import com.otterworks.rating.service.RatingTables;
import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

class RatingServiceTest {

    private final RatingProperties props = new RatingProperties("../legacy-rating/tables", null);
    private final RatingService rating = new RatingService(new RatingTables(props), props);

    private Quote rate(String record) {
        return rating.rate(PolicyRecordReader.read(record));
    }

    @Test
    void ratesAGeneralLiabilityPolicy() {
        Quote q = rate("P0000001GLIL913400002026031500002100{050100500N00{00NNN");
        assertThat(q.status()).isEqualTo("OK");
        assertThat(q.basePremium()).isEqualByComparingTo("871.50");
        assertThat(q.total()).isEqualByComparingTo("906.50");
    }

    @Test
    void floorsAtTheMinimumPremium() {
        Quote q = rate("P0000004GLIL185010002026031500002100{050100500N00{00NNN");
        assertThat(q.minimumApplied()).isTrue();
        assertThat(q.modifiedPremium()).isEqualByComparingTo("500.00");
    }

    @Test
    void rejectsZeroExposure() {
        assertThat(rate("P0000009GLIL9134000020260315000000000050100500N00{00NNN").reason()).isEqualTo("EX");
    }

    @Test
    void readsNegativeOverpunch() {
        assertThat(PolicyRecordReader.read("P0000009GLIL913400002026031500002100}050100500N00{00NNN").exposure())
                .isEqualByComparingTo(new BigDecimal("-210.00"));
    }

    // Parity pins: each record is the fixture line from legacy-rating/fixtures/policies.dat and the
    // expected values are the executed COBOL and Pharo outputs (see parity/report.md).

    @Test
    void classRateIsInForceOnItsEndDate() {
        // R02/R19: GL/41650 row ends 2026-06-30 and is still in force that day.
        Quote q = rate("P0000028GLIL416500102026063000004000{050100500N00{00NNN");
        assertThat(q.status()).isEqualTo("OK");
        assertThat(q.basePremium()).isEqualByComparingTo("798.00");
        assertThat(q.factorSource()).isEqualTo("T");
    }

    @Test
    void territoryIsInForceOnItsEndDate() {
        // R02/R36: GL/040 at 1.200 ends 2026-06-30.
        Quote q = rate("P0000027GLIL913400402026063000003000{050100500N00{00NNN");
        assertThat(q.basePremium()).isEqualByComparingTo("1494.00");
        assertThat(q.factorSource()).isEqualTo("T");
    }

    @Test
    void overrideIsInForceOnItsEndDate() {
        // R02/R51: GL/91580/040 override ends 2026-12-31.
        Quote q = rate("P0000032GLIL915800402026123100001505{050100500N00{00NNN");
        assertThat(q.basePremium()).isEqualByComparingTo("1399.65");
        assertThat(q.factorSource()).isEqualTo("O");
    }

    @Test
    void overrideMustMatchTheRequestedTerritory() {
        // R49/R50: the GL/91580 override is for territory 040 only; territory 000 keeps its factor.
        Quote q = rate("P0000002GLIL915800002026031500002100{050100500N00{00NNN");
        assertThat(q.basePremium()).isEqualByComparingTo("1302.00");
        assertThat(q.factorSource()).isEqualTo("T");
    }

    @Test
    void roundsExposureTimesRateBeforeTheTerritoryFactor() {
        // R54: rounding only after both multiplications would give 450.98.
        Quote q = rate("P0000092PRNY0702 0402026111000007541D050105000Y01}00NNN");
        assertThat(q.basePremium()).isEqualByComparingTo("450.97");
        assertThat(q.modifiedPremium()).isEqualByComparingTo("354.73");
    }

    @Test
    void roundsTheBasePremiumHalfUp() {
        // R55: 555.50 x 0.950 = 527.725.
        Quote q = rate("P0000065GLIL185010102026031500005050{050100500Y02}00NNN");
        assertThat(q.basePremium()).isEqualByComparingTo("527.73");
    }

    @Test
    void roundsEachModifierHalfUpToTheCent() {
        // R61: 575.10 x 0.95 = 546.345.
        Quote q = rate("P0000050PRIL0900 0102026031500009000{050102500N00{00NNN");
        assertThat(q.modifiedPremium()).isEqualByComparingTo("546.35");
        assertThat(q.total()).isEqualByComparingTo("581.35");
    }

    @Test
    void appliesTheMinimumAfterScheduleAndMultiPolicy() {
        // R82, owner decision: COBOL order (RATEPREM 3500-MINIMUM-PREMIUM after 3300/3400).
        Quote floored = rate("P0000065GLIL185010102026031500005050{050100500Y02}00NNN");
        assertThat(floored.modifiedPremium()).isEqualByComparingTo("500.00");
        assertThat(floored.minimumApplied()).isTrue();
        Quote surcharged = rate("P0000067GLIL185010002026031500004200{050100500N02{00NNN");
        assertThat(surcharged.modifiedPremium()).isEqualByComparingTo("554.40");
        assertThat(surcharged.minimumApplied()).isFalse();
    }

    @Test
    void chargesEndorsementsInTheTotal() {
        // R84, owner decision: Pharo charges endorsements; R90 equipment 3% of 4160.00 = 124.80 -> $125.
        Quote q = rate("P0000071PRIL0702 0002026031500080000{050100500N00{00YNN");
        assertThat(q.endorsements()).isEqualByComparingTo("125.00");
        assertThat(q.total()).isEqualByComparingTo("4320.00");
    }

    @Test
    void roundsTheEquipmentChargeToCentsBeforeDollars() {
        // R89/R90: 3% of 11583.29 = 347.4987 -> 347.50 -> $348 (whole dollars straight from 347.4987 give $347).
        Quote q = rate("P0000159PRIL0900 0302026100700083530A030400250N02E00YNN");
        assertThat(q.modifiedPremium()).isEqualByComparingTo("11583.29");
        assertThat(q.endorsements()).isEqualByComparingTo("348.00");
    }

    @Test
    void capsEndorsementsAtAQuarterRoundedHalfUp() {
        // R97: 25% of 723.73 = 180.9325 -> 180.93.
        Quote q = rate("P0000170GLTX913400402026030100001610C000200500Y00N02NYY");
        assertThat(q.endorsements()).isEqualByComparingTo("180.93");
        assertThat(q.total()).isEqualByComparingTo("939.66");
    }
}
