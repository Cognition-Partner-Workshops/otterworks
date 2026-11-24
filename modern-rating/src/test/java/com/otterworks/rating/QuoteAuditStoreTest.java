package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.config.RatingProperties;
import com.otterworks.rating.model.PolicyRecordReader;
import com.otterworks.rating.model.Quote;
import com.otterworks.rating.service.RatingService;
import com.otterworks.rating.service.RatingTables;
import java.util.Locale;
import org.apache.commons.collections.map.LRUMap;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
class QuoteAuditStoreTest {

    @Autowired
    private QuoteAuditStore audit;

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
    void evictsTheLeastRecentlyUsedPolicyButKeepsItsStoredQuote() {
        Quote first = rate("P0000100GLIL913400002026031500002100{050100500N00{00NNN");
        Quote second = rate("P0000101GLIL913400002026031500002100{050100500N00{00NNN");
        String firstReference = audit.save(first);
        String secondReference = audit.save(second);
        for (int policy = 102; policy < 150; policy++) {
            audit.save(rate(String.format(Locale.ROOT,
                    "P%07dGLIL913400002026031500002100{050100500N00{00NNN", policy)));
        }

        assertThat(audit.policyFor(firstReference)).isEqualTo(first.policyId());
        audit.save(rate("P0000150GLIL913400002026031500002100{050100500N00{00NNN"));

        assertThat(audit.policyFor(firstReference)).isEqualTo(first.policyId());
        assertThat(audit.policyFor(secondReference)).isNull();
        assertThat(audit.find(secondReference)).containsExactly(second.asLine());
    }

    @Test
    void loadsThePatchedCommonsCollectionsVersion() {
        assertThat(LRUMap.class.getPackage().getImplementationVersion()).isEqualTo("3.2.2");
    }

    @Test
    void findsNothingForAnUnknownReference() {
        assertThat(audit.find("ABCDEF123456")).isEmpty();
    }

    @Test
    void findsOnlyTheQuoteWithTheRequestedReference() {
        Quote first = rate("P0000001GLIL913400002026031500002100{050100500N00{00NNN");
        Quote second = rate("P0000004GLIL185010002026031500002100{050100500N00{00NNN");
        String firstReference = audit.save(first);
        String secondReference = audit.save(second);

        assertThat(audit.find(firstReference)).containsExactly(first.asLine());
        assertThat(audit.find(secondReference)).containsExactly(second.asLine());
    }

    @Test
    void treatsAnApostropheInAnUnknownReferenceAsLiteralText() {
        Quote quote = rate("P0000001GLIL913400002026031500002100{050100500N00{00NNN");
        String reference = audit.save(quote);

        assertThat(audit.find("O'Brien")).isEmpty();
        assertThat(audit.find(reference)).containsExactly(quote.asLine());
    }
}
