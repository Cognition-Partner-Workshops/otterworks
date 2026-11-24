package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.util.Base64;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class QuoteRestoreIT {

    /** Harmless marker: records whether anything ever Java-deserialized it. */
    static class DeserializationCanary implements Serializable {
        private static final long serialVersionUID = 1L;
        static final AtomicBoolean READ = new AtomicBoolean();

        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            in.defaultReadObject();
            READ.set(true);
        }
    }

    @Autowired
    private TestRestTemplate http;

    @BeforeEach
    void resetCanary() {
        DeserializationCanary.READ.set(false);
    }

    private HttpHeaders headers(MediaType type) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-Support-Key", "insrules-support");
        headers.setContentType(type);
        return headers;
    }

    private static String serializedCanary() throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(new DeserializationCanary());
        }
        return Base64.getEncoder().encodeToString(bytes.toByteArray());
    }

    @Test
    void restoresAParkedQuoteFromJson() {
        String body = "{\"reference\":\"A1B2C3D4E5F6\",\"fields\":{\"line\":\"GL\",\"state\":\"IL\"}}";
        var restored = http.postForEntity("/admin/quotes/restore",
                new HttpEntity<>(body, headers(MediaType.APPLICATION_JSON)), String.class);
        assertThat(restored.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(restored.getBody()).isEqualTo("A1B2C3D4E5F6");
    }

    @Test
    void refusesAParkedQuoteWithoutAReference() {
        var restored = http.postForEntity("/admin/quotes/restore",
                new HttpEntity<>("{\"fields\":{}}", headers(MediaType.APPLICATION_JSON)), String.class);
        assertThat(restored.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void refusesWithoutTheSupportKey() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        var restored = http.postForEntity("/admin/quotes/restore",
                new HttpEntity<>("{\"reference\":\"A1B2C3D4E5F6\"}", headers), String.class);
        assertThat(restored.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void neverJavaDeserializesABase64Body() throws IOException {
        String parked = serializedCanary();

        var asText = http.postForEntity("/admin/quotes/restore",
                new HttpEntity<>(parked, headers(MediaType.TEXT_PLAIN)), String.class);
        assertThat(asText.getStatusCode()).isEqualTo(HttpStatus.UNSUPPORTED_MEDIA_TYPE);

        var asJson = http.postForEntity("/admin/quotes/restore",
                new HttpEntity<>("\"" + parked + "\"", headers(MediaType.APPLICATION_JSON)), String.class);
        assertThat(asJson.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);

        assertThat(DeserializationCanary.READ).isFalse();
    }
}
