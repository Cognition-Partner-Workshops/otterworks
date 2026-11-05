package com.bank.rates;

import static org.junit.Assert.*;
import java.nio.file.*;
import java.util.*;
import org.junit.Test;

public class DisclosureTest {
    @Test
    public void everyCsvRateHasAnImmediatelyAdjacentSourceBusinessDate() throws Exception {
        Path root = Files.createDirectories(Paths.get("target", "fs09_" + UUID.randomUUID()));
        Path in = Files.createDirectory(root.resolve("fs09_in"));
        Path out = Files.createDirectory(root.resolve("fs09_out"));
        Files.write(in.resolve("ticks-2026-10-14.csv"), Arrays.asList("timestamp,pair,bid,ask",
                "2026-10-14T00:00:00Z,EURUSD,1.0800,1.0802"));
        RatesJob.main(new String[] {in.toString(), out.toString(), "2026-10-14"});
        List<String> rows = Files.readAllLines(out.resolve("rates-2026-10-14.csv"));
        List<String> columns = Arrays.asList(rows.get(0).split(","));
        String[] values = rows.get(1).split(",");
        for (String rate : Arrays.asList("open", "high", "low", "close", "avg_mid")) {
            int index = columns.indexOf(rate);
            assertEquals("Business date must be beside " + rate, rate + "_business_date", columns.get(index + 1));
            assertEquals("2026-10-14", values[index + 1]);
        }
        Files.write(in.resolve("ticks-2026-10-15.csv"), Collections.singletonList("timestamp,pair,bid,ask"));
        RatesJob.main(new String[] {in.toString(), out.toString(), "2026-10-15"});
        assertEquals(1, Files.readAllLines(out.resolve("rates-2026-10-15.csv")).size());
        assertThrows(RuntimeException.class, () -> RatesJob.businessDate(new String[] {"in", "out", "not-a-date"}));
    }
}
