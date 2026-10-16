package com.otterworks.legacyportal.lambda.feedback;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;

public final class FeedbackService {
    private final FeedbackRepository repository;

    public FeedbackService(FeedbackRepository repository) {
        this.repository = repository;
    }

    public Feedback submit(String userId, int rating, String message) {
        Instant createdAt = Instant.now().truncatedTo(ChronoUnit.MICROS);
        return repository.save(new Feedback(null, userId, rating, message, createdAt));
    }

    public List<Feedback> listForUser(String userId) {
        return repository.findByUserId(userId);
    }

    public double averageRating() {
        FeedbackRepository.FeedbackAggregates values = repository.aggregate();
        if (values.count() == 0) {
            return 0.0;
        }
        return (double) values.ratingSum() / values.count();
    }
}
