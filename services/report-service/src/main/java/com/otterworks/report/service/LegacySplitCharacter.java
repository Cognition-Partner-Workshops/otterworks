package com.otterworks.report.service;

import com.lowagie.text.SplitCharacter;
import com.lowagie.text.pdf.PdfChunk;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Preserves iText 5's date-aware line wrapping. */
final class LegacySplitCharacter implements SplitCharacter {

    private static final Pattern DATE_PATTERN = Pattern.compile("(\\d{2,4}-\\d{2}-\\d{2,4})");

    static final LegacySplitCharacter INSTANCE = new LegacySplitCharacter();

    private LegacySplitCharacter() {
    }

    @Override
    public boolean isSplitCharacter(int start, int current, int end, char[] cc, PdfChunk[] ck) {
        char[] ccTmp = checkDatePattern(String.valueOf(cc));
        char c = getCurrentCharacter(current, ccTmp, ck);

        if (c <= ' ' || c == '-' || c == '\u2010') {
            return true;
        }
        if (c < 0x2002) {
            return false;
        }
        return (c >= 0x2002 && c <= 0x200b)
                || (c >= 0x2e80 && c < 0xd7a0)
                || (c >= 0xf900 && c < 0xfb00)
                || (c >= 0xfe30 && c < 0xfe50)
                || (c >= 0xff61 && c < 0xffa0);
    }

    private char getCurrentCharacter(int current, char[] cc, PdfChunk[] ck) {
        return ck == null ? cc[current] : (char) ck[Math.min(current, ck.length - 1)]
                .getUnicodeEquivalent(cc[current]);
    }

    private char[] checkDatePattern(String data) {
        if (data.contains("-")) {
            Matcher m = DATE_PATTERN.matcher(data);
            if (m.find()) {
                String tmpData = m.group(1).replace('-', '\u2011');
                data = data.replaceAll(m.group(1), tmpData);
            }
        }
        return data.toCharArray();
    }
}
