package com.otterworks.ottershops.engage;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class ReviewServiceTest {
    @Test
    void newRatingFoldsIntoRunningAverage() {
        assertEquals(4.5, ReviewService.foldRating(4.5, 100, 5));
        assertEquals(3.0, ReviewService.foldRating(5.0, 1, 1));
        assertEquals(4.0, ReviewService.foldRating(0, 0, 4));
    }

    @Test
    void fitVerdictNeedsAMajority() {
        assertNull(ReviewService.verdict(new int[]{0, 0, 0}));
        assertEquals("Runs small: consider sizing up", ReviewService.verdict(new int[]{3, 1, 1}));
        assertEquals("Runs large: consider sizing down", ReviewService.verdict(new int[]{0, 1, 2}));
        assertEquals("Fits true to size", ReviewService.verdict(new int[]{2, 2, 0}));
    }

    @Test
    void trimDropsBlankAndCapsLength() {
        assertNull(ReviewService.trim("   ", 10));
        assertEquals("abc", ReviewService.trim("  abcdef ", 3));
    }
}
