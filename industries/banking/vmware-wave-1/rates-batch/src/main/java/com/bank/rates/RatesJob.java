package com.bank.rates;

import java.io.IOException;
import java.io.Writer;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Clock;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Stream;

/**
 * Nightly reference rates. Reads the day's hourly ticks and writes one line per
 * currency pair with open, high, low, close and the average mid.
 * Usage: RatesJob <in-dir> <out-dir> [yyyy-MM-dd]
 * Without arguments the directories come from RATES_IN and RATES_OUT and the
 * date from RATES_DAY. The default date is yesterday in RATES_TZ (else the JVM zone).
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

    static Map<String, Daily> aggregate(List<String> lines) {
        Map<String, Daily> out = new TreeMap<>();
        for (String line : lines) {
            if (line.isBlank() || line.startsWith("timestamp,")) continue;
            String[] f = line.split(",");
            BigDecimal bid = new BigDecimal(f[2].trim());
            BigDecimal ask = new BigDecimal(f[3].trim());
            BigDecimal mid = bid.add(ask).divide(BigDecimal.valueOf(2), 6, RoundingMode.HALF_EVEN);
            out.computeIfAbsent(f[1].trim(), Daily::new).add(mid);
        }
        return out;
    }

    static ZoneId zone(Map<String, String> env) {
        String tz = env.get("RATES_TZ");
        return tz == null || tz.isBlank() ? ZoneId.systemDefault() : ZoneId.of(tz);
    }

    static LocalDate businessDate(String[] args, Clock clock) {
        if (args.length > 2) return LocalDate.parse(args[2]);
        return LocalDate.now(clock).minusDays(1);
    }

    static String[] resolveArgs(String[] args, Map<String, String> env) {
        if (args.length > 0) return args;
        String in = env.get("RATES_IN"), out = env.get("RATES_OUT"), day = env.get("RATES_DAY");
        if (in == null || in.isBlank() || out == null || out.isBlank()) return args;
        return day == null || day.isBlank() ? new String[] {in, out} : new String[] {in, out, day};
    }

    public static void main(String[] cliArgs) throws IOException {
        Map<String, String> env = System.getenv();
        String[] args = resolveArgs(cliArgs, env);
        if (args.length < 2) {
            System.err.println("usage: RatesJob <in-dir> <out-dir> [yyyy-MM-dd]");
            System.exit(2);
        }
        Path in = Paths.get(args[0]);
        Path outDir = Paths.get(args[1]);
        String day = businessDate(args, Clock.system(zone(env))).format(DateTimeFormatter.ISO_LOCAL_DATE);
        Path ticks = in.resolve("ticks-" + day + ".csv");
        if (!Files.exists(ticks)) {
            System.err.println("no ticks for " + day + " in " + in);
            System.exit(1);
        }
        List<String> lines;
        try (Stream<String> s = Files.lines(ticks, StandardCharsets.UTF_8)) {
            lines = new ArrayList<>();
            s.forEach(lines::add);
        }
        Map<String, Daily> rates = aggregate(lines);
        Files.createDirectories(outDir);
        Path tmp = outDir.resolve(".rates-" + day + ".tmp");
        try (Writer w = Files.newBufferedWriter(tmp, StandardCharsets.UTF_8)) {
            w.write("pair,open,high,low,close,avg_mid,ticks\n");
            for (Daily d : rates.values()) w.write(d.csv() + "\n");
        }
        Files.move(tmp, outDir.resolve("rates-" + day + ".csv"), StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING);
        System.out.println("rates " + day + ": " + rates.size() + " pairs written to " + outDir);
    }
}
