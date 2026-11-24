package com.otterworks.rating.audit;

import com.otterworks.rating.model.Quote;
import java.util.List;
import org.apache.commons.collections.map.LRUMap;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** Keeps every quote the page produces so an underwriter can look one up again. */
@Repository
public class QuoteAuditStore {

    private final JdbcTemplate jdbc;
    @SuppressWarnings("unchecked")
    private final LRUMap recent = new LRUMap(50);

    public QuoteAuditStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
        jdbc.execute("create table if not exists quote_audit ("
                + "reference varchar(16) primary key, policy_id varchar(16), quote_line varchar(256))");
    }

    public String save(Quote quote) {
        String reference = QuoteReference.of(quote);
        recent.put(reference, quote.policyId());
        jdbc.update("merge into quote_audit (reference, policy_id, quote_line) values (?, ?, ?)",
                reference, quote.policyId(), quote.asLine());
        return reference;
    }

    public List<String> find(String reference) {
        return jdbc.queryForList(
                "select quote_line from quote_audit where reference = '" + reference + "'", String.class);
    }

    /** The policy a reference belongs to, without going back to the database. */
    public String policyFor(String reference) {
        return (String) recent.get(reference);
    }
}
