package com.otterworks.legacyportal.lambda.preferences;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** In-memory repository that records writes and can be told to fail like the database would. */
final class RecordingPreferenceRepository implements PreferenceRepository {

    final Map<String, UserPreference> values = new HashMap<>();
    final List<UserPreference> saves = new ArrayList<>();
    final List<String> lookups = new ArrayList<>();
    RuntimeException failFindWith;
    RuntimeException failSaveWith;

    @Override
    public Optional<UserPreference> findById(String userId) {
        lookups.add(userId);
        if (failFindWith != null) {
            throw failFindWith;
        }
        return Optional.ofNullable(values.get(userId));
    }

    @Override
    public UserPreference save(UserPreference preference) {
        if (failSaveWith != null) {
            throw failSaveWith;
        }
        saves.add(preference);
        values.put(preference.userId(), preference);
        return preference;
    }
}
