package com.otterworks.legacyportal.lambda.preferences;

public record UserPreference(
        String userId, String theme, String locale, boolean emailNotifications) {}
