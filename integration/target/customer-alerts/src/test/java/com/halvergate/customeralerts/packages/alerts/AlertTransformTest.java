package com.halvergate.customeralerts.packages.alerts;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import java.io.StringReader;
import java.io.StringWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import javax.xml.transform.stream.StreamResult;
import javax.xml.transform.stream.StreamSource;
import net.sf.saxon.TransformerFactoryImpl;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.yaml.snakeyaml.Yaml;

class AlertTransformTest {
    @SuppressWarnings("unchecked")
    @ParameterizedTest
    @ValueSource(strings = {"card-dispute", "large-transaction", "low-balance"})
    void transformsFrozenCorpus(String flow) throws Exception {
        Map<String, Object> corpus = new Yaml().load(Files.readString(
            Path.of("../../corpus/customer-alerts." + flow + "/flow.json")));
        var inputs = (List<Map<String, Object>>) ((Map<?, ?>) corpus.get("inputs")).get("messages");
        var expected = (Map<String, Object>) corpus.get("expected");
        var messages = (List<Map<String, Object>>) expected.get("messages");
        var rows = (Map<String, List<Map<String, Object>>>) expected.get("db");
        var stylesheet = getClass().getResource("/packages/alerts/Transforms/" + flow + ".xsl");
        var templates = new TransformerFactoryImpl().newTemplates(new StreamSource(stylesheet.toExternalForm()));
        for (var input : inputs) {
            var output = new StringWriter();
            templates.newTransformer().transform(new StreamSource(new StringReader((String) input.get("body"))),
                new StreamResult(output));
            var record = AlertRecord.parse(output.toString());
            var properties = (Map<String, String>) input.get("properties");
            var matching = messages.stream().filter(message -> {
                var headers = (Map<String, String>) message.get("headers");
                return properties.get("requestId").equals(headers.get("requestId"))
                    && !message.get("destination").equals("HB.UNDLV");
            }).toList();
            if (record.filtered()) {
                assertThat(matching).isEmpty();
            } else {
                assertThat(matching).isNotEmpty().allSatisfy(message ->
                    assertThat(record.body()).isEqualTo(message.get("body")));
                for (var table : rows.values()) {
                    table.stream().filter(row -> row.get("request_id").equals(record.id())).forEach(row -> {
                        assertThat(record.account()).isEqualTo(row.get("account_id"));
                        assertThat(record.amount()).isEqualTo(row.get("amount"));
                        assertThat(record.currency()).isEqualTo(row.get("currency"));
                        assertThat(record.status()).isEqualTo(row.get("status"));
                    });
                }
            }
        }
    }

    @ParameterizedTest
    @ValueSource(strings = {"card-dispute.xsl", "large-transaction.xsl", "low-balance.xsl", "common/receipt.xsl"})
    void stylesheetsAreByteIdentical(String file) throws Exception {
        try (var copy = getClass().getResourceAsStream("/packages/alerts/Transforms/" + file)) {
            assertThat(copy.readAllBytes()).isEqualTo(Files.readAllBytes(Path.of("../../legacy-bw6/Transforms/" + file)));
        }
    }

    @Test
    void emptyResultHasNoBody() throws Exception {
        assertThat(AlertRecord.parse("<result/> ").body()).isEmpty();
    }

    @Test
    void malformedResultFails() {
        assertThatThrownBy(() -> AlertRecord.parse("<result>" )).isInstanceOf(org.xml.sax.SAXException.class);
    }

    @Test
    void externalEntitiesAreRejected() {
        assertThatThrownBy(() -> AlertRecord.parse("<!DOCTYPE result SYSTEM 'file:///not-read'><result/>"))
            .isInstanceOf(org.xml.sax.SAXException.class);
    }
}
