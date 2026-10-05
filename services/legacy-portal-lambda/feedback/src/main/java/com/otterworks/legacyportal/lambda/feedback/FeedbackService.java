package com.otterworks.legacyportal.lambda.feedback;

import java.time.Clock;
import java.time.Instant;
import java.util.List;
import java.util.Objects;

public class FeedbackService {

    private static final int MIN_RATING = 1;
    private static final int MAX_RATING = 5;

    private final FeedbackStore store;
    private final Clock clock;

    public FeedbackService(FeedbackStore store) {
        this(store, Clock.systemUTC());
    }

    FeedbackService(FeedbackStore store, Clock clock) {
        this.store = Objects.requireNonNull(store);
        this.clock = Objects.requireNonNull(clock);
    }

    public Feedback submit(String userId, int rating, String message) {
        if (rating < MIN_RATING || rating > MAX_RATING) {
            throw new IllegalArgumentException(
                    "rating must be between " + MIN_RATING + " and " + MAX_RATING);
        }
        Instant createdAt = Instant.now(clock);
        createdAt = Instant.ofEpochSecond(createdAt.getEpochSecond(),
                (createdAt.getNano() / 1_000) * 1_000L);
        return store.save(new Feedback(null, userId, rating, message, createdAt));
    }

    public List<Feedback> listForUser(String userId) {
        return store.findByUserIdOrderByCreatedAtDesc(userId);
    }

    public double averageRating() {
        return store.averageRating();
    }
}
