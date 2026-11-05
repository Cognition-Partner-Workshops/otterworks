package com.bank.rates;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class RatesJobTest {

    @Rule
    public TemporaryFolder tmp = new TemporaryFolder();

    private static Clock at(String instant) {
        return Clock.fixed(Instant.parse(instant), ZoneOffset.UTC);
    }

    private static Map<String, String> env(String... kv) {
        Map<String, String> m = new HashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put(kv[i], kv[i + 1]);
        return m;
    }

    @Test
    public void aggregatesMidPerPair() {
        Map<String, RatesJob.Daily> r = RatesJob.aggregate(Arrays.asList(
                "timestamp,pair,bid,ask",
                "2026-10-14T00:00:00Z,EURUSD,1.0800,1.0802",
                "2026-10-14T01:00:00Z,EURUSD,1.0810,1.0812",
                "2026-10-14T02:00:00Z,EURUSD,1.0790,1.0792",
                "2026-10-14T00:00:00Z,EURGBP,0.8600,0.8602"));
        assertEquals(2, r.size());
        assertEquals("EURUSD,1.080100,1.081100,1.079100,1.079100,1.080100,3", r.get("EURUSD").csv());
        assertEquals("EURGBP,0.860100,0.860100,0.860100,0.860100,0.860100,1", r.get("EURGBP").csv());
    }

    @Test
    public void businessDateIsYesterdayInTheConfiguredZoneAcrossTheDayBoundary() {
        ZoneId utc = ZoneId.of("Etc/UTC");
        assertEquals(LocalDate.parse("2026-10-15"), RatesJob.businessDate(null, utc, at("2026-10-16T23:59:59Z")));
        assertEquals(LocalDate.parse("2026-10-16"), RatesJob.businessDate(null, utc, at("2026-10-17T00:00:00Z")));
        assertEquals(LocalDate.parse("2026-10-16"), RatesJob.businessDate(null, utc, at("2026-10-17T02:00:00Z")));
    }

    @Test
    public void sameInstantGivesADifferentBusinessDateInAnotherZone() {
        Clock c = at("2026-10-16T23:30:00Z");
        assertEquals(LocalDate.parse("2026-10-15"), RatesJob.businessDate(null, ZoneId.of("Etc/UTC"), c));
        assertEquals(LocalDate.parse("2026-10-16"), RatesJob.businessDate(null, ZoneId.of("Europe/Berlin"), c));
        assertEquals(LocalDate.parse("2026-10-14"), RatesJob.businessDate(null, ZoneId.of("America/Los_Angeles"),
                at("2026-10-16T06:59:59Z")));
    }

    @Test
    public void zoneDefaultsToTheJvmDefaultLikeTheVm() {
        assertEquals(ZoneId.systemDefault(), RatesJob.zone(env()));
        assertEquals(ZoneId.systemDefault(), RatesJob.zone(env("BUSINESS_DATE_ZONE", " ")));
        assertEquals(ZoneId.of("Europe/London"), RatesJob.zone(env("BUSINESS_DATE_ZONE", "Europe/London")));
    }

    @Test
    public void explicitDateWinsOverTheClock() throws Exception {
        Clock c = at("2026-11-05T02:00:00Z");
        assertEquals(LocalDate.parse("2026-10-15"),
                RatesJob.Config.from(new String[] {"in", "out", "2026-10-15"}, env(), c).day);
        assertEquals(LocalDate.parse("2026-10-14"),
                RatesJob.Config.from(new String[0], env("RATES_IN", "i", "RATES_OUT", "o",
                        "RATES_BUSINESS_DATE", "2026-10-14"), c).day);
        RatesJob.Config fromEnv = RatesJob.Config.from(new String[0],
                env("RATES_IN", "i", "RATES_OUT", "o", "BUSINESS_DATE_ZONE", "Etc/UTC"), c);
        assertEquals(LocalDate.parse("2026-11-04"), fromEnv.day);
        assertEquals("i", fromEnv.in);
        assertEquals("o", fromEnv.out);
    }

    @Test(expected = RatesJob.ConfigException.class)
    public void missingSpoolsIsAConfigurationError() throws Exception {
        RatesJob.Config.from(new String[0], env("RATES_IN", "i"), at("2026-11-05T02:00:00Z"));
    }

    @Test
    public void directorySpoolsWriteTheReportAtomically() throws Exception {
        Path in = tmp.newFolder("in").toPath();
        Path out = tmp.getRoot().toPath().resolve("out");
        Files.writeString(in.resolve("ticks-2026-10-14.csv"),
                "timestamp,pair,bid,ask\n2026-10-14T00:00:00Z,EURUSD,1.0800,1.0802\n");
        int rc = RatesJob.run(new RatesJob.Config(in.toString(), out.toString(), LocalDate.parse("2026-10-14")));
        assertEquals(0, rc);
        assertEquals("pair,open,high,low,close,avg_mid,ticks\nEURUSD,1.080100,1.080100,1.080100,1.080100,1.080100,1\n",
                Files.readString(out.resolve("rates-2026-10-14.csv")));
        assertFalse(Files.exists(out.resolve(".rates-2026-10-14.tmp")));
    }

    @Test
    public void missingTicksFailsTheRun() throws Exception {
        Path in = tmp.newFolder("empty").toPath();
        assertNull(RatesJob.readTicks(in.toString(), "ticks-2026-10-14.csv"));
        assertEquals(1, RatesJob.run(new RatesJob.Config(in.toString(), tmp.getRoot().toString(),
                LocalDate.parse("2026-10-14"))));
    }

    @Test
    public void httpSpoolsReadTicksAndPutTheReport() throws Exception {
        Map<String, byte[]> store = new ConcurrentHashMap<>();
        store.put("/in/ticks-2026-10-15.csv",
                "timestamp,pair,bid,ask\n2026-10-15T00:00:00Z,EURGBP,0.8600,0.8602\n".getBytes(StandardCharsets.UTF_8));
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", ex -> {
            String path = ex.getRequestURI().getPath();
            if ("PUT".equals(ex.getRequestMethod())) {
                store.put(path, ex.getRequestBody().readAllBytes());
                ex.sendResponseHeaders(201, -1);
            } else if (store.containsKey(path)) {
                byte[] b = store.get(path);
                ex.sendResponseHeaders(200, b.length);
                ex.getResponseBody().write(b);
            } else {
                ex.sendResponseHeaders(404, -1);
            }
            ex.close();
        });
        server.start();
        try {
            String base = "http://127.0.0.1:" + server.getAddress().getPort();
            assertEquals(0, RatesJob.run(new RatesJob.Config(base + "/in", base + "/out/", LocalDate.parse("2026-10-15"))));
            assertEquals("pair,open,high,low,close,avg_mid,ticks\nEURGBP,0.860100,0.860100,0.860100,0.860100,0.860100,1\n",
                    new String(store.get("/out/rates-2026-10-15.csv"), StandardCharsets.UTF_8));
            assertEquals(1, RatesJob.run(new RatesJob.Config(base + "/in", base + "/out", LocalDate.parse("2026-10-16"))));
            List<String> none = RatesJob.readTicks(base + "/in", "ticks-2026-10-16.csv");
            assertNull(none);
        } finally {
            server.stop(0);
        }
    }
}
