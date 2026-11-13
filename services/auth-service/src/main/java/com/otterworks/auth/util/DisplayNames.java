package com.otterworks.auth.util;

import java.util.Locale;
import org.apache.commons.text.WordUtils;

/** Avatar initials for clients that show a user before their avatar image loads. */
public final class DisplayNames {

  private static final int MAX_INITIALS = 2;

  private DisplayNames() {}

  public static String initials(String displayName, String email) {
    String source = displayName;
    if (source == null || source.isBlank()) {
      source = localPart(email);
    }
    if (source == null || source.isBlank()) {
      return "";
    }
    String letters = WordUtils.initials(source.trim(), ' ', '.', '_', '-');
    if (letters.length() > MAX_INITIALS) {
      letters = letters.charAt(0) + letters.substring(letters.length() - 1);
    }
    return letters.toUpperCase(Locale.ROOT);
  }

  private static String localPart(String email) {
    if (email == null) {
      return null;
    }
    int at = email.indexOf('@');
    return at < 0 ? email : email.substring(0, at);
  }
}
