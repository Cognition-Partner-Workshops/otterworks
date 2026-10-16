package com.otterworks.legacyportal.lambda.feedback;

import java.time.Instant;

public record Feedback(Long id, String userId, int rating, String message, Instant createdAt) {
}
