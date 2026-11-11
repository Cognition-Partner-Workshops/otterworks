package com.halvergate.payments;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.StringReader;
import java.io.StringWriter;
import java.nio.file.Path;
import javax.xml.transform.stream.StreamResult;
import javax.xml.transform.stream.StreamSource;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import net.sf.saxon.TransformerFactoryImpl;
import org.junit.jupiter.api.Test;
import org.w3c.dom.Element;

class InstructionTransformTest {
    static JsonNode corpus() throws Exception {
        return new ObjectMapper().readTree(Path.of("../../corpus/payments.instruction-intake/flow.json").toFile());
    }

    @Test
    void transformsEveryFrozenInputWithImportPrecedence() throws Exception {
        JsonNode corpus = corpus();
        var stylesheet = getClass().getResource("/Transforms/payment-status.xsl");
        var templates = new TransformerFactoryImpl().newTemplates(new StreamSource(stylesheet.toExternalForm()));
        for (int i = 0; i < corpus.path("inputs").path("messages").size(); i++) {
            StringWriter output = new StringWriter();
            templates.newTransformer().transform(
                new StreamSource(new StringReader(corpus.path("inputs").path("messages").get(i).path("body").asText())),
                new StreamResult(output));
            Element result = InstructionIntakeRoute.result(output.toString());
            JsonNode expected = corpus.path("expected").path("db").path("payment_inbox").get(i);
            assertThat(InstructionIntakeRoute.text(result, "body"))
                .isEqualTo(corpus.path("expected").path("messages").get(i).path("body").asText());
            assertThat(InstructionIntakeRoute.text(result, "status")).isEqualTo(expected.path("status").asText());
            assertThat(InstructionIntakeRoute.text(result, "amount")).isEqualTo(expected.path("amount").asText());
            assertThat(result.getAttribute("currency")).isEqualTo(expected.path("currency").asText());
        }
    }
}
