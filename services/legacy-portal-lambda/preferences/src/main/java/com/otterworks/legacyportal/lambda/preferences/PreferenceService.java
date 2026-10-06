package com.otterworks.legacyportal.lambda.preferences;

public final class PreferenceService {

    static final String DEFAULT_THEME = "light";
    static final String DEFAULT_LOCALE = "en-US";

    private final PreferenceRepository repository;

    public PreferenceService(PreferenceRepository repository) {
        this.repository = repository;
    }

    public UserPreference getOrDefault(String userId) {
        return repository
                .findById(userId)
                .orElseGet(() -> new UserPreference(userId, DEFAULT_THEME, DEFAULT_LOCALE, true));
    }

    public UserPreference save(
            String userId, String theme, String locale, boolean emailNotifications) {
        UserPreference preference =
                repository
                        .findById(userId)
                        .orElseGet(
                                () ->
                                        new UserPreference(
                                                userId, DEFAULT_THEME, DEFAULT_LOCALE, true));
        return repository.save(
                new UserPreference(userId, theme, locale, emailNotifications));
    }
}
