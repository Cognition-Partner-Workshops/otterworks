package com.bank.rates;

import java.io.IOException;
import java.io.Writer;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CharsetDecoder;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.*;

/**
 * Nightly reference rates. Reads the day's hourly ticks and writes one line per
 * currency pair with open, high, low, close and the average mid.
 * Usage: RatesJob <in-dir> <out-dir> [yyyy-MM-dd]
 */
public class RatesJob {

    public static final class Daily {
        final String pair;
        BigDecimal open, high, low, close, sum = BigDecimal.ZERO;
        int n;

        Daily(String pair) { this.pair = pair; }

        void add(BigDecimal mid) {
            if (open == null) { open = mid; high = mid; low = mid; }
            high = high.max(mid);
            low = low.min(mid);
            close = mid;
            sum = sum.add(mid);
            n++;
        }

        BigDecimal avg() { return sum.divide(BigDecimal.valueOf(n), 6, RoundingMode.HALF_EVEN); }

        String csv() {
            return String.join(",", pair, open.toPlainString(), high.toPlainString(), low.toPlainString(),
                    close.toPlainString(), avg().toPlainString(), String.valueOf(n));
        }
    }

    private static final java.util.regex.Pattern PAIR = java.util.regex.Pattern.compile("[A-Z]{6}");

    static Map<String, Daily> aggregate(List<String> lines) {
        return aggregate(lines, new ArrayList<>());
    }

    /**
     * Skips rows that cannot be read as a tick and adds one note per skipped row to {@code rejected}.
     * A {@code null} entry is a row that was not valid UTF-8 (see {@link #readLines}).
     */
    static Map<String, Daily> aggregate(List<String> lines, List<String> rejected) {
        Map<String, Daily> out = new TreeMap<>();
        int lineNo = 0;
        for (String line : lines) {
            lineNo++;
            if (line == null) {
                rejected.add("line " + lineNo + ": contains bytes that are not UTF-8");
                continue;
            }
            if (line.isBlank() || line.startsWith("timestamp,")) continue;
            String[] f = line.split(",");
            if (f.length < 4) {
                rejected.add("line " + lineNo + ": expected 4 fields, found " + f.length);
                continue;
            }
            String pair = f[1].trim();
            if (!PAIR.matcher(pair).matches()) {
                rejected.add("line " + lineNo + ": pair is not six letters A-Z");
                continue;
            }
            BigDecimal bid;
            BigDecimal ask;
            try {
                bid = new BigDecimal(f[2].trim());
                ask = new BigDecimal(f[3].trim());
            } catch (NumberFormatException e) {
                rejected.add("line " + lineNo + ": bid or ask is not a number");
                continue;
            }
            BigDecimal mid = bid.add(ask).divide(BigDecimal.valueOf(2), 6, RoundingMode.HALF_EVEN);
            out.computeIfAbsent(pair, Daily::new).add(mid);
        }
        return out;
    }

    /**
     * Splits on \n, \r or \r\n like {@link java.io.BufferedReader#readLine} and decodes each row as strict
     * UTF-8. A row with an invalid byte sequence becomes {@code null} so only that row is lost.
     */
    static List<String> readLines(byte[] bytes) {
        CharsetDecoder utf8 = StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT);
        List<String> lines = new ArrayList<>();
        int start = 0;
        int i = 0;
        while (i < bytes.length) {
            byte b = bytes[i];
            if (b == '\n' || b == '\r') {
                lines.add(decode(utf8, bytes, start, i));
                i += (b == '\r' && i + 1 < bytes.length && bytes[i + 1] == '\n') ? 2 : 1;
                start = i;
            } else {
                i++;
            }
        }
        if (start < bytes.length) lines.add(decode(utf8, bytes, start, bytes.length));
        return lines;
    }

    private static String decode(CharsetDecoder utf8, byte[] bytes, int from, int to) {
        try {
            return utf8.reset().decode(ByteBuffer.wrap(bytes, from, to - from)).toString();
        } catch (CharacterCodingException e) {
            return null;
        }
    }

    static LocalDate businessDate(String[] args) {
        if (args.length > 2) return LocalDate.parse(args[2]);
        return LocalDate.now().minusDays(1);
    }

    public static void main(String[] args) throws IOException {
        if (args.length < 2) {
            System.err.println("usage: RatesJob <in-dir> <out-dir> [yyyy-MM-dd]");
            System.exit(2);
        }
        Path in = Paths.get(args[0]);
        Path outDir = Paths.get(args[1]);
        String day = businessDate(args).format(DateTimeFormatter.ISO_LOCAL_DATE);
        Path ticks = in.resolve("ticks-" + day + ".csv");
        if (!Files.exists(ticks)) {
            System.err.println("no ticks for " + day + " in " + in);
            System.exit(1);
        }
        List<String> lines = readLines(Files.readAllBytes(ticks));
        List<String> rejected = new ArrayList<>();
        Map<String, Daily> rates = aggregate(lines, rejected);
        for (String note : rejected) System.err.println("rates " + day + ": skipped " + note);
        Files.createDirectories(outDir);
        Path tmp = outDir.resolve(".rates-" + day + ".tmp");
        try (Writer w = Files.newBufferedWriter(tmp, StandardCharsets.UTF_8)) {
            w.write("pair,open,high,low,close,avg_mid,ticks\n");
            for (Daily d : rates.values()) w.write(d.csv() + "\n");
        }
        Files.move(tmp, outDir.resolve("rates-" + day + ".csv"), StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING);
        System.out.println("rates " + day + ": " + rates.size() + " pairs written to " + outDir
                + (rejected.isEmpty() ? "" : " (" + rejected.size() + " malformed rows skipped)"));
    }
}
