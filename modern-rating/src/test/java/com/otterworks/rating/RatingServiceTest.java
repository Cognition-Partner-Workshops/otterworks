package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.config.RatingProperties;
import com.otterworks.rating.model.PolicyRecordReader;
import com.otterworks.rating.model.Quote;
import com.otterworks.rating.service.RatingService;
import com.otterworks.rating.service.RatingTables;
import java.io.IOException;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

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

    @ParameterizedTest
    @CsvSource({
        "P0000027GLIL913400402026063000003000{050100500N00{00NNN, T, 1494.00",
        "P0000028GLIL416500102026063000004000{050100500N00{00NNN, T, 798.00",
        "P0000032GLIL915800402026123100001505{050100500N00{00NNN, O, 1399.65",
        "P0000037CAIL7219 0202026093000000040{050100500N00{00NNN, O, 8990.00"
    })
    void includesTheLastEffectiveDay(String record, String source, String base) {
        Quote q = rate(record);
        assertThat(q.status()).isEqualTo("OK");
        assertThat(q.factorSource()).isEqualTo(source);
        assertThat(q.basePremium()).isEqualByComparingTo(base);
    }

    @Test
    void ignoresAnOverrideForADifferentTerritory() {
        Quote q = rate("P0000033GLIL915800202026041000001505{050100500N00{00NNN");
        assertThat(q.factorSource()).isEqualTo("T");
        assertThat(q.basePremium()).isEqualByComparingTo("1026.41");
    }

    @ParameterizedTest
    @CsvSource({
        "P0000050PRIL0900 0102026031500009000{050102500N00{00NNN, 575.10, 546.35",
        "P0000076GLNY416500102026081800020253I070105000Y00E01NNN, 4329.27, 4318.44",
        "P0000089PRNY0702 0402026122400032610D150005000Y00E00YNN, 1950.10, 1610.64",
        "P0000092PRNY0702 0402026111000007541D050105000Y01}00NNN, 450.97, 354.73",
        "P0000097PRTX0702 0302026051000079937F010405000N02E00NNN, 6650.82, 9560.56"
    })
    void roundsHalfCentsUpAtEachPremiumStep(String record, String base, String modified) {
        Quote q = rate(record);
        assertThat(q.basePremium()).isEqualByComparingTo(base);
        assertThat(q.modifiedPremium()).isEqualByComparingTo(modified);
    }

    @ParameterizedTest
    @CsvSource({
        "P0000065GLIL185010102026031500005050{050100500Y02}00NNN, 500.00, true",
        "P0000066PRIL0311 0002026031500009500{060000500Y01N00NNN, 350.00, true",
        "P0000067GLIL185010002026031500004200{050100500N02{00NNN, 554.40, false"
    })
    void floorsAfterScheduleAndPackageAdjustments(String record, String modified, boolean minimum) {
        Quote q = rate(record);
        assertThat(q.modifiedPremium()).isEqualByComparingTo(modified);
        assertThat(q.minimumApplied()).isEqualTo(minimum);
    }

    @ParameterizedTest
    @CsvSource({
        "P0000069GLIL913400002026031500003000{050100500N00{05NNY, 270.00, 1550.00",
        "P0000073GLIL185010002026031500004600{050100500N00{03YYY, 126.50, 667.50",
        "P0000159PRIL0900 0302026100700083530A030400250N02E00YNN, 348.00, 11966.29",
        "P0000200GLCA185010992026011200004541F010000250N01}00NYN, 15.00, 800.00"
    })
    void chargesPharoEndorsementsOnTheFinalPremium(String record, String endorsements, String total) {
        Quote q = rate(record);
        assertThat(q.endorsements()).isEqualByComparingTo(endorsements);
        assertThat(q.total()).isEqualByComparingTo(total);
    }

    @Test
    void usesTheLastFloridaWindFactorRegardlessOfDate(@TempDir Path tablesDir) throws IOException {
        try (var files = Files.list(Path.of(props.tablesDir()))) {
            for (Path file : files.toList()) {
                Files.copy(file, tablesDir.resolve(file.getFileName()));
            }
        }
        Files.writeString(tablesDir.resolve("territory-factors.dat"),
                "PR|WND|1.250|20260101|\nPR|WND|1.500|20270101|\n", StandardOpenOption.APPEND);
        RatingProperties windProps = new RatingProperties(tablesDir.toString(), props.policyFee());
        RatingService windRating = new RatingService(new RatingTables(windProps), windProps);
        var policy = PolicyRecordReader.read("P0000148PRFL0702 0602026052400070497E080100500N00{00NNN");
        assertThat(rating.rate(policy).modifiedPremium()).isEqualByComparingTo("3665.87");
        assertThat(windRating.rate(policy).modifiedPremium()).isEqualByComparingTo("5498.81");
    }
}
