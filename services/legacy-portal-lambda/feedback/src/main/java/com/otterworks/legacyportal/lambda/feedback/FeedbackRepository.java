package com.otterworks.legacyportal.lambda.feedback;

import java.util.List;

public interface FeedbackRepository {
    Feedback save(Feedback feedback);

    List<Feedback> findByUserId(String userId);

    FeedbackAggregates aggregate();

    record FeedbackAggregates(long count, long ratingSum) {
    }
}
