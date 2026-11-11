package com.halvergate.payments.packages.returns;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.StringReader;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.xml.transform.dom.DOMResult;
import javax.xml.transform.stream.StreamSource;
import net.sf.saxon.TransformerFactoryImpl;
import org.junit.jupiter.api.Test;
import org.w3c.dom.Document;
import org.w3c.dom.Element;

class ReturnsTransformTest {
    static JsonNode corpus() throws Exception {
        return new ObjectMapper().readTree(Path.of("../../corpus/payments.payment-returns/flow.json").toFile());
    }

    @Test
    void stylesheetClosureIsByteIdenticalToLegacy() throws Exception {
        for (String name : new String[]{"payment-returns.xsl", "common/receipt.xsl"}) {
            var copy = getClass().getResourceAsStream("/packages/returns/Transforms/" + name).readAllBytes();
            assertThat(copy).as(name).isEqualTo(Files.readAllBytes(Path.of("../../legacy-bw6/Transforms/" + name)));
        }
    }

    @Test
    void corpusInputsProjectToExpectedRowsAndBodies() throws Exception {
        JsonNode corpus = corpus();
        var stylesheet = getClass().getResource("/packages/returns/Transforms/payment-returns.xsl");
        var templates = new TransformerFactoryImpl().newTemplates(new StreamSource(stylesheet.toExternalForm()));
        JsonNode inputs = corpus.path("inputs").path("messages");
        assertThat(inputs.size()).isEqualTo(2);
        for (int i = 0; i < inputs.size(); i++) {
            DOMResult out = new DOMResult();
            templates.newTransformer().transform(new StreamSource(new StringReader(inputs.get(i).path("body").asText())), out);
            Element result = ((Document) out.getNode()).getDocumentElement();
            JsonNode row = corpus.path("expected").path("db").path("payment_returns").get(i);
            assertThat(result.getAttribute("id")).isEqualTo(row.path("request_id").asText());
            assertThat(result.getAttribute("account")).isEqualTo(row.path("account_id").asText());
            assertThat(result.getAttribute("currency")).isEqualTo(row.path("currency").asText());
            assertThat(PaymentReturnsRoute.text(result, "amount")).isEqualTo(row.path("amount").asText());
            assertThat(PaymentReturnsRoute.text(result, "status")).isEqualTo(row.path("status").asText());
            assertThat(PaymentReturnsRoute.text(result, "body"))
                .isEqualTo(corpus.path("expected").path("messages").get(i).path("body").asText());
        }
    }

    @Test
    void requestCurrencyWinsOverEmbeddedDocumentCurrency() throws Exception {
        JsonNode second = corpus().path("inputs").path("messages").get(1);
        assertThat(second.path("body").asText()).contains("currency=\"EUR\"").contains("Ccy=\"USD\"");
        assertThat(corpus().path("expected").path("db").path("payment_returns").get(1).path("currency").asText())
            .isEqualTo("EUR");
    }
}
