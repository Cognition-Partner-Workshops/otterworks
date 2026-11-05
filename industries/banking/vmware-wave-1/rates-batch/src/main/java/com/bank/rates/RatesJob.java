package com.bank.rates;

import java.io.IOException;
import java.io.InputStream;
import java.io.Writer;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URI;
import java.net.ConnectException;
import java.net.UnknownHostException;
import java.net.http.HttpClient;
import java.net.http.HttpConnectTimeoutException;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Clock;
import java.time.Duration;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.function.LongSupplier;

/**
 * Nightly reference rates. Reads the day's hourly ticks and writes one line per
 * currency pair with open, high, low, close and the average mid.
 *
 * Usage: RatesJob [in out [yyyy-MM-dd]]
 * Without arguments the job reads its configuration from the environment:
 *   RATES_IN, RATES_OUT      directory or http(s) base URL of the input and output spools
 *   RATES_BUSINESS_DATE      explicit business date (yyyy-MM-dd), for reruns
 *   BUSINESS_DATE_ZONE       zone that defines "yesterday"; the JVM default zone when unset
 */
public class RatesJob {

    static final String HEADER = "pair,open,high,low,close,avg_mid,ticks\n";

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

    static final class ConfigException extends Exception {
        ConfigException(String message) { super(message); }
    }

    static final class Config {
        final String in;
        final String out;
        final LocalDate day;

        Config(String in, String out, LocalDate day) { this.in = in; this.out = out; this.day = day; }

        static Config from(String[] args, Map<String, String> env, Clock clock) throws ConfigException {
            String in = args.length > 0 ? args[0] : env.get("RATES_IN");
            String out = args.length > 1 ? args[1] : env.get("RATES_OUT");
            if (blank(in) || blank(out)) {
                throw new ConfigException("usage: RatesJob <in> <out> [yyyy-MM-dd], or set RATES_IN and RATES_OUT");
            }
            String explicit = args.length > 2 ? args[2] : env.get("RATES_BUSINESS_DATE");
            return new Config(in, out, businessDate(explicit, zone(env), clock));
        }

        private static boolean blank(String s) { return s == null || s.isBlank(); }
    }

    static ZoneId zone(Map<String, String> env) {
        String z = env.get("BUSINESS_DATE_ZONE");
        return z == null || z.isBlank() ? ZoneId.systemDefault() : ZoneId.of(z.trim());
    }

    static LocalDate businessDate(String explicit, ZoneId zone, Clock clock) {
        if (explicit != null && !explicit.isBlank()) return LocalDate.parse(explicit.trim());
        return LocalDate.now(clock.withZone(zone)).minusDays(1);
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

    static String report(Map<String, Daily> rates) {
        StringBuilder sb = new StringBuilder(HEADER);
        for (Daily d : rates.values()) sb.append(d.csv()).append('\n');
        return sb.toString();
    }

    static boolean isUrl(String location) {
        return location.startsWith("http://") || location.startsWith("https://");
    }

    private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();

    interface HttpAttempt<T> {
        T send(Duration timeout) throws IOException, InterruptedException;
    }

    interface Sleeper {
        void sleep(long millis) throws InterruptedException;
    }

    static long retryMillis(Map<String, String> env) {
        String value = env.getOrDefault("RATES_HTTP_RETRY_SECONDS", "30");
        long seconds = Long.parseLong(value);
        if (seconds < 0 || seconds > 300) throw new IllegalArgumentException("RATES_HTTP_RETRY_SECONDS must be 0..300");
        return seconds * 1000;
    }

    static <T> T retryHttp(HttpAttempt<T> attempt, long budgetMillis, Sleeper sleeper, LongSupplier nanoTime)
            throws IOException, InterruptedException {
        long start = nanoTime.getAsLong();
        long delay = 1000;
        int retries = 0;
        while (true) {
            long remaining = budgetMillis - (nanoTime.getAsLong() - start) / 1_000_000;
            try {
                return attempt.send(Duration.ofMillis(budgetMillis == 0 ? 30000 : Math.max(1, remaining)));
            } catch (IOException e) {
                if (!(e instanceof ConnectException || e instanceof UnknownHostException
                        || e instanceof HttpConnectTimeoutException)) throw e;
                remaining = budgetMillis - (nanoTime.getAsLong() - start) / 1_000_000;
                if (remaining <= delay) throw e;
                System.err.println("HTTP spool transport retry " + (++retries) + " in " + delay
                        + "ms: " + e.getClass().getSimpleName());
                sleeper.sleep(delay);
                delay = Math.min(delay * 2, 4000);
            }
        }
    }

    private static <T> HttpResponse<T> send(HttpRequest.Builder request, HttpResponse.BodyHandler<T> handler)
            throws IOException, InterruptedException {
        return retryHttp(timeout -> HTTP.send(request.timeout(timeout).build(), handler),
                retryMillis(System.getenv()), Thread::sleep, System::nanoTime);
    }

    private static URI child(String base, String name) {
        return URI.create(base.endsWith("/") ? base + name : base + "/" + name);
    }

    /** Returns the tick lines, or null when the day has no tick file. */
    static List<String> readTicks(String in, String name) throws IOException, InterruptedException {
        String body;
        if (isUrl(in)) {
            HttpResponse<String> r = send(HttpRequest.newBuilder(child(in, name)).GET(),
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (r.statusCode() == 404) return null;
            if (r.statusCode() != 200) throw new IOException("GET " + child(in, name) + " returned " + r.statusCode());
            body = r.body();
        } else {
            Path ticks = Paths.get(in).resolve(name);
            if (!Files.exists(ticks)) return null;
            body = Files.readString(ticks, StandardCharsets.UTF_8);
        }
        return body.lines().collect(java.util.stream.Collectors.toList());
    }

    static void writeReport(String out, String name, String content) throws IOException, InterruptedException {
        if (isUrl(out)) {
            HttpResponse<Void> r = send(HttpRequest.newBuilder(child(out, name))
                    .header("Content-Type", "text/csv")
                    .PUT(HttpRequest.BodyPublishers.ofString(content, StandardCharsets.UTF_8)),
                    HttpResponse.BodyHandlers.discarding());
            if (r.statusCode() / 100 != 2) throw new IOException("PUT " + child(out, name) + " returned " + r.statusCode());
            return;
        }
        Path outDir = Paths.get(out);
        Files.createDirectories(outDir);
        Path tmp = outDir.resolve("." + name.replaceFirst("\\.csv$", "") + ".tmp");
        try (Writer w = Files.newBufferedWriter(tmp, StandardCharsets.UTF_8)) {
            w.write(content);
        }
        Files.move(tmp, outDir.resolve(name), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }

    static int run(Config c) throws IOException, InterruptedException {
        String day = c.day.format(DateTimeFormatter.ISO_LOCAL_DATE);
        List<String> lines = readTicks(c.in, "ticks-" + day + ".csv");
        if (lines == null) {
            System.err.println("no ticks for " + day + " in " + c.in);
            return 1;
        }
        Map<String, Daily> rates = aggregate(lines);
        writeReport(c.out, "rates-" + day + ".csv", report(rates));
        System.out.println("rates " + day + ": " + rates.size() + " pairs written to " + c.out);
        return 0;
    }

    public static void main(String[] args) throws IOException, InterruptedException {
        Config c;
        try {
            c = Config.from(args, System.getenv(), Clock.systemUTC());
        } catch (ConfigException e) {
            System.err.println(e.getMessage());
            System.exit(2);
            return;
        }
        System.exit(run(c));
    }
}
