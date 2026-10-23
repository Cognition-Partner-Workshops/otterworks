package com.otterworks.report.service;

import com.lowagie.text.SplitCharacter;
import com.lowagie.text.pdf.DefaultSplitCharacter;
import com.lowagie.text.pdf.PdfChunk;

import java.util.regex.Pattern;

/**
 * iText 5's line-breaking rule for table cells, so OpenPDF wraps long values where iText 5 did.
 *
 * iText 5.5 never breaks a chunk that contains a date ({@code 2026-01-15T03:31:00Z} is wrapped where
 * the cell runs out of width); OpenPDF breaks it after a hyphen ({@code 2026-01-} / {@code 15T...}).
 * Otherwise OpenPDF's default rule applies.
 */
final class Itext5SplitCharacter implements SplitCharacter {

    static final SplitCharacter INSTANCE = new Itext5SplitCharacter();

    private static final Pattern DATE_PATTERN = Pattern.compile("(\\d{2,4}-\\d{2}-\\d{2,4})");

    private Itext5SplitCharacter() {
    }

    @Override
    public boolean isSplitCharacter(int start, int current, int end, char[] cc, PdfChunk[] ck) {
        if (DATE_PATTERN.matcher(new String(cc, start, end - start)).find()) {
            return false;
        }
        return DefaultSplitCharacter.DEFAULT.isSplitCharacter(start, current, end, cc, ck);
    }
}
