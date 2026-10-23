package com.otterworks.report.service;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class LegacySplitCharacterTest {

    @Test
    void doesNotSplitAtHyphensWithinDates() {
        char[] cc = "2026-01-15T03:45:00Z".toCharArray();

        assertFalse(LegacySplitCharacter.INSTANCE.isSplitCharacter(0, 4, cc.length, cc, null));
    }

    @Test
    void splitsAtHyphensOutsideDates() {
        char[] cc = "plain-text".toCharArray();

        assertTrue(LegacySplitCharacter.INSTANCE.isSplitCharacter(0, 5, cc.length, cc, null));
    }

    @Test
    void splitsAtSpaces() {
        char[] cc = "plain text".toCharArray();

        assertTrue(LegacySplitCharacter.INSTANCE.isSplitCharacter(0, 5, cc.length, cc, null));
    }
}
