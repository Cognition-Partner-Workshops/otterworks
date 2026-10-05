package com.otterworks.legacyportal.lambda.feedback;

import java.util.List;

public interface FeedbackStore {

    Feedback save(Feedback feedback);

    List<Feedback> findByUserIdOrderByCreatedAtDesc(String userId);

    double averageRating();
}
