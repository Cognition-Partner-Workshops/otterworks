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

        assertThat(reference).hasSize(16);
        assertThat(audit.find(reference)).containsExactly(quote.asLine());
        assertThat(audit.policyFor(reference)).isEqualTo("P0000001");
    }

    @Test
    void givesTheSameQuoteTheSameReferenceTwice() {
        Quote quote = rate("P0000004GLIL185010002026031500002100{050100500N00{00NNN");

        assertThat(audit.save(quote)).isEqualTo(audit.save(quote));
        assertThat(audit.find(audit.save(quote))).hasSize(1);
    }

    @Test
    void issuesASha256ReferenceAndKeepsExistingReferencesReadable() {
        Quote quote = Quote.refused("P0000009", "REJ", "EX");
        String oldReference = "4D2B9C6E80E3";
        jdbc.update("insert into quote_audit (reference, policy_id, quote_line) values (?, ?, ?)",
                oldReference, quote.policyId(), quote.asLine());

        String reference = audit.save(quote);

        assertThat(reference).isEqualTo("1C424ABD4D7864DE");
        assertThat(audit.find(reference)).containsExactly(quote.asLine());
        assertThat(audit.find(oldReference)).containsExactly(quote.asLine());
    }

    @Test
    void findsNothingForAnUnknownReference() {
        assertThat(audit.find("ABCDEF123456")).isEmpty();
    }
}
