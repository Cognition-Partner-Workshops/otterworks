package com.otterworks.rating.service;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class RatingBatchRunnerTest {

    @Test
    void usesAnUppercaseTwelveCharacterSha256Prefix() {
        assertThat(RatingBatchRunner.digest("abc")).isEqualTo("BA7816BF8F01");
    }
}
