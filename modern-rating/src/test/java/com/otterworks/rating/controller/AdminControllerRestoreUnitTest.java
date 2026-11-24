package com.otterworks.rating.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.config.RatingProperties;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;

class AdminControllerRestoreUnitTest {

    private static final String SUPPORT_KEY = "insrules-support";
    private static final byte[] LEGACY_FORMAT_HEADER = {(byte) 0xAC, (byte) 0xED, 0x00, 0x05};

    private final AdminController controller = new AdminController(mock(RatingProperties.class),
            mock(QuoteAuditStore.class));

    @Test
    void identifiesTheLegacyHeaderButNotJson() {
        assertThat(AdminController.isLegacySerializedFormat(LEGACY_FORMAT_HEADER)).isTrue();
        assertThat(AdminController.isLegacySerializedFormat("{\"reference\":\"Q-123\"}"
                .getBytes(StandardCharsets.UTF_8))).isFalse();
    }

    @Test
    void explainsHowToReplaceAnUnsupportedLegacyQuote() {
        var response = controller.restore(Base64.getEncoder().encodeToString(LEGACY_FORMAT_HEADER), SUPPORT_KEY);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getHeaders().getContentType()).isEqualTo(MediaType.TEXT_PLAIN);
        assertThat(response.getBody()).isEqualTo(
                "Unsupported parked quote format: serialized Java objects are no longer accepted; park the quote as JSON.");
    }

    @Test
    void rejectsNonBase64Text() {
        var response = controller.restore("not base64", SUPPORT_KEY);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).isNull();
    }

    @ParameterizedTest
    @ValueSource(strings = {"parked quote", "{\"fields\":{}}"})
    void rejectsDecodedTextWithoutAJsonReference(String content) {
        String parked = Base64.getEncoder().encodeToString(content.getBytes(StandardCharsets.UTF_8));
        var response = controller.restore(parked, SUPPORT_KEY);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).isNull();
    }
}
