package com.bank.rates;

import static org.junit.Assert.assertEquals;

import java.util.Arrays;
import java.util.Map;
import org.junit.Test;

public class RatesJobTest {
    @Test public void yesterdayUsesExplicitClockZone() {
        java.time.Instant instant = java.time.Instant.parse("2026-10-16T23:30:00Z");
        assertEquals(java.time.LocalDate.parse("2026-10-15"), RatesJob.businessDate(new String[0],
                java.time.Clock.fixed(instant, java.time.ZoneId.of("Etc/UTC"))));
        assertEquals(java.time.LocalDate.parse("2026-10-16"), RatesJob.businessDate(new String[0],
                java.time.Clock.fixed(instant, java.time.ZoneId.of("Asia/Tokyo"))));
        assertEquals(java.time.LocalDate.parse("2026-10-14"), RatesJob.businessDate(new String[]{"in", "out", "2026-10-14"},
                java.time.Clock.fixed(instant, java.time.ZoneId.of("Asia/Tokyo"))));
    }

    @Test public void emptyTicksHaveNoPairs() { assertEquals(0, RatesJob.aggregate(Arrays.asList("timestamp,pair,bid,ask", "")).size()); }

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
}
