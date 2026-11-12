package app.synthetic.insurance.iri;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertThrows;

class SchemaAssertionsTest {
    @Test
    void acceptsValidBody() throws Exception {
        SchemaAssertions.assertValid("Error", "{\"code\":\"policy.inquiry.notFound\",\"message\":\"Not found\"}");
        SchemaAssertions.assertValid("PolicyValue", "{\"valuesAsOfDate\":\"2026-06-30\",\"accountValues\":{\"endingAccountValue\":1}}");
    }

    @Test
    void rejectsInvalidBody() {
        assertThrows(AssertionError.class, () -> SchemaAssertions.assertValid("Error", "{\"code\":\"bad\"}"));
        assertThrows(AssertionError.class, () -> SchemaAssertions.assertValid("PolicySummary", "{}"));
        assertThrows(AssertionError.class, () -> SchemaAssertions.assertValid("PolicyValue", "{\"valuesAsOfDate\":\"not-a-date\",\"accountValues\":{\"endingAccountValue\":1}}"));
    }
}
