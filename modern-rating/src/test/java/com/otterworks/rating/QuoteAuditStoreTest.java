package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.config.RatingProperties;
import com.otterworks.rating.model.PolicyRecordReader;
import com.otterworks.rating.model.Quote;
import com.otterworks.rating.service.RatingService;
import com.otterworks.rating.service.RatingTables;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

@SpringBootTest
class QuoteAuditStoreTest {

    @Autowired
    private QuoteAuditStore audit;

    @Autowired
    private JdbcTemplate jdbc;

    private final RatingProperties props = new RatingProperties("../legacy-rating/tables", null);
    private final RatingService rating = new RatingService(new RatingTables(props), props);

    private Quote rate(String record) {
        return rating.rate(PolicyRecordReader.read(record));
    }

    @Test
    void savesAQuoteAndFindsItAgainByReference() {
        Quote quote = rate("P0000001GLIL913400002026031500002100{050100500N00{00NNN");
        String reference = audit.save(quote);

        assertThat(reference).hasSize(12);
        assertThat(quote.asLine()).isEqualTo("P0000001|OK||87150|87150|N|0|3500|90650|T");
        assertThat(reference).isEqualTo("1D807AA35ABC");
        assertThat(audit.find(reference)).containsExactly(quote.asLine());
        assertThat(audit.policyFor(reference)).isEqualTo("P0000001");
    }

    @Test
    void findsAnExistingReferenceAfterSavingTheSameQuoteWithTheNewDigest() {
        Quote quote = rate("P0000001GLIL913400002026031500002100{050100500N00{00NNN");
        String oldReference = "347073A078DF";
        jdbc.update("insert into quote_audit (reference, policy_id, quote_line) values (?, ?, ?)",
                oldReference, quote.policyId(), quote.asLine());

        assertThat(audit.save(quote)).isNotEqualTo(oldReference);
        assertThat(audit.find(oldReference)).containsExactly(quote.asLine());
    }

    @Test
    void givesTheSameQuoteTheSameReferenceTwice() {
        Quote quote = rate("P0000004GLIL185010002026031500002100{050100500N00{00NNN");

        assertThat(audit.save(quote)).isEqualTo(audit.save(quote));
        assertThat(audit.find(audit.save(quote))).hasSize(1);
    }

    @Test
    void findsNothingForAnUnknownReference() {
        assertThat(audit.find("ABCDEF123456")).isEmpty();
    }
}
