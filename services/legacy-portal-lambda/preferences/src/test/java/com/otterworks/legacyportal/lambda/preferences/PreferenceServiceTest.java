package com.otterworks.legacyportal.lambda.preferences;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class PreferenceServiceTest {

    private RecordingPreferenceRepository repository;
    private PreferenceService service;

    @BeforeEach
    void setUp() {
        repository = new RecordingPreferenceRepository();
        service = new PreferenceService(repository);
    }

    @Test
    void readingDefaultsForANewUserDoesNotCreateARow() {
        UserPreference preference = service.getOrDefault("new-user");

        assertEquals(new UserPreference("new-user", "light", "en-US", true), preference);
        assertTrue(repository.saves.isEmpty());
        assertTrue(repository.values.isEmpty());
    }

    @Test
    void storedPreferencesWinOverDefaults() {
        UserPreference stored = new UserPreference("u1", "dark", "fr-FR", false);
        repository.values.put("u1", stored);

        assertSame(stored, service.getOrDefault("u1"));
    }

    @Test
    void saveReplacesEveryFieldOfAnExistingPreference() {
        repository.values.put("u1", new UserPreference("u1", "dark", "fr-FR", true));

        UserPreference saved = service.save("u1", "light", "de-DE", false);

        assertEquals(new UserPreference("u1", "light", "de-DE", false), saved);
        assertEquals(saved, repository.values.get("u1"));
    }

    @Test
    void saveIsScopedToTheTargetUser() {
        UserPreference other = new UserPreference("u2", "dark", "fr-FR", true);
        repository.values.put("u2", other);

        service.save("u1", "light", "de-DE", false);

        assertSame(other, repository.values.get("u2"));
        assertEquals(1, repository.saves.size());
        assertEquals("u1", repository.saves.get(0).userId());
    }

    @Test
    void repositoryFailuresPropagateInsteadOfFallingBackToDefaults() {
        repository.failFindWith = new IllegalStateException("database down");

        assertThrows(IllegalStateException.class, () -> service.getOrDefault("u1"));
    }

    @Test
    void failedWriteIsNotReportedAsSaved() {
        repository.failSaveWith = new IllegalStateException("database down");

        assertThrows(
                IllegalStateException.class, () -> service.save("u1", "dark", "fr-FR", false));
        assertTrue(repository.values.isEmpty());
    }
}
