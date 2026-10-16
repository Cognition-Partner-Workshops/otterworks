package com.otterworks.legacyportal.lambda.preferences;

import java.util.Optional;

public interface PreferenceRepository {

    Optional<UserPreference> findById(String userId);

    UserPreference save(UserPreference preference);
}
