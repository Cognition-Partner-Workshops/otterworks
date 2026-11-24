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
}
