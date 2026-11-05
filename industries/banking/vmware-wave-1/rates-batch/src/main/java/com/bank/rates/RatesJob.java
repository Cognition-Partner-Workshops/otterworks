package com.bank.rates;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.Clock;
import java.time.ZoneId;
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

    static LocalDate businessDate(String[] args) {
        String zone = System.getenv("BUSINESS_TZ");
        return businessDate(args, Clock.system(zone == null || zone.isEmpty() ? ZoneId.systemDefault() : ZoneId.of(zone)));
    }

    static LocalDate businessDate(String[] args, Clock clock) {
        if (args.length > 2) return LocalDate.parse(args[2]);
        return LocalDate.now(clock).minusDays(1);
    }

    public static void main(String[] args) throws IOException {
        if (args.length < 2) {
            System.err.println("usage: RatesJob <in-dir> <out-dir> [yyyy-MM-dd]");
            System.exit(2);
        }
        Storage in = Storage.open(args[0]);
        Storage outDir = Storage.open(args[1]);
        String day = businessDate(args).format(DateTimeFormatter.ISO_LOCAL_DATE);
        byte[] ticks = in.read("ticks-" + day + ".csv");
        if (ticks == null) {
            System.err.println("no ticks for " + day + " in " + in);
            System.exit(1);
        }
        List<String> lines = new ArrayList<>();
        StandardCharsets.UTF_8.newDecoder().decode(java.nio.ByteBuffer.wrap(ticks)).toString().lines().forEach(lines::add);
        Map<String, Daily> rates = aggregate(lines);
        StringBuilder csv = new StringBuilder("pair,open,high,low,close,avg_mid,ticks\n");
        for (Daily d : rates.values()) csv.append(d.csv()).append('\n');
        outDir.write("rates-" + day + ".csv", csv.toString().getBytes(StandardCharsets.UTF_8));
        System.out.println("rates " + day + ": " + rates.size() + " pairs written to " + outDir);
    }
}
