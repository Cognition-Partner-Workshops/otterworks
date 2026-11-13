package com.otterworks.auth.util;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class DisplayNamesTest {

  @Test
  void usesFirstAndLastWordOfDisplayName() {
    assertThat(DisplayNames.initials("Ada Lovelace", "ada@otterworks.io")).isEqualTo("AL");
    assertThat(DisplayNames.initials("mary ann evans", "m@otterworks.io")).isEqualTo("ME");
  }

  @Test
  void singleWordGivesOneLetter() {
    assertThat(DisplayNames.initials("otter", "o@otterworks.io")).isEqualTo("O");
  }

  @Test
  void fallsBackToEmailLocalPart() {
    assertThat(DisplayNames.initials(null, "grace.hopper@otterworks.io")).isEqualTo("GH");
    assertThat(DisplayNames.initials("  ", "linus_t@otterworks.io")).isEqualTo("LT");
  }

  @Test
  void emptyWhenNothingToUse() {
    assertThat(DisplayNames.initials(null, null)).isEmpty();
  }
}
