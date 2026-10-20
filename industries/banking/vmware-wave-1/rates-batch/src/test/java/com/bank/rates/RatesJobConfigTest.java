package com.bank.rates;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.Map;
import org.junit.Test;

public class RatesJobConfigTest {

    private static final String[] NONE = new String[0];

    @Test
    public void zoneFromRatesTz() {
        assertEquals(ZoneId.of("Europe/London"), RatesJob.zone(Map.of("RATES_TZ", "Europe/London")));
        assertEquals(ZoneId.systemDefault(), RatesJob.zone(Map.of()));
        assertEquals(ZoneId.systemDefault(), RatesJob.zone(Map.of("RATES_TZ", " ")));
    }

    @Test
    public void yesterdayIsTakenInTheConfiguredZone() {
        Instant at = Instant.parse("2026-10-16T23:30:00Z");
        assertEquals(LocalDate.parse("2026-10-15"),
                RatesJob.businessDate(NONE, Clock.fixed(at, ZoneId.of("UTC"))));
        assertEquals(LocalDate.parse("2026-10-16"),
                RatesJob.businessDate(NONE, Clock.fixed(at, ZoneId.of("Asia/Tokyo"))));
    }

    @Test
    public void cronAtTwoLocalAcrossDstEnd() {
        // 2026-10-25 02:00 Europe/London is the morning the clocks go back.
        ZoneId london = ZoneId.of("Europe/London");
        Instant at = LocalDate.parse("2026-10-25").atTime(2, 0).atZone(london).toInstant();
        assertEquals(LocalDate.parse("2026-10-24"), RatesJob.businessDate(NONE, Clock.fixed(at, london)));
    }

    @Test
    public void explicitDateWins() {
        Clock c = Clock.fixed(Instant.parse("2026-10-20T02:00:00Z"), ZoneId.of("UTC"));
        assertEquals(LocalDate.parse("2026-10-14"), RatesJob.businessDate(new String[] {"a", "b", "2026-10-14"}, c));
    }

    @Test
    public void argsWinOverEnv() {
        String[] args = {"/in", "/out"};
        assertArrayEquals(args, RatesJob.resolveArgs(args, Map.of("RATES_IN", "/x", "RATES_OUT", "/y")));
    }

    @Test
    public void envSuppliesDirsAndDay() {
        assertArrayEquals(new String[] {"/x", "/y"},
                RatesJob.resolveArgs(NONE, Map.of("RATES_IN", "/x", "RATES_OUT", "/y")));
        assertArrayEquals(new String[] {"/x", "/y", "2026-10-16"},
                RatesJob.resolveArgs(NONE, Map.of("RATES_IN", "/x", "RATES_OUT", "/y", "RATES_DAY", "2026-10-16")));
    }

    @Test
    public void incompleteEnvKeepsUsageError() {
        assertEquals(0, RatesJob.resolveArgs(NONE, Map.of("RATES_IN", "/x")).length);
        assertEquals(0, RatesJob.resolveArgs(NONE, Map.of()).length);
    }
}
