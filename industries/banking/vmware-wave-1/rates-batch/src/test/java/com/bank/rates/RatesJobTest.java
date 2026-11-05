package com.bank.rates;

import static org.junit.Assert.assertEquals;

import java.util.Arrays;
import java.util.Map;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.junit.Rule;
import org.junit.rules.TemporaryFolder;
import static org.junit.Assert.assertTrue;
import org.junit.Test;

public class RatesJobTest {
    @Rule
    public TemporaryFolder tmp = new TemporaryFolder();

    @Test
    public void outputCarriesBusinessDateOnEveryRateRow() throws Exception {
        Path in = tmp.newFolder("in").toPath();
        Path out = tmp.newFolder("out").toPath();
        Files.write(in.resolve("ticks-2026-10-14.csv"), Arrays.asList(
                "timestamp,pair,bid,ask",
                "2026-10-14T00:00:00Z,EURUSD,1.0800,1.0802",
                "2026-10-14T00:00:00Z,EURGBP,0.8600,0.8602"), StandardCharsets.UTF_8);
        RatesJob.main(new String[] { in.toString(), out.toString(), "2026-10-14" });
        List<String> rows = Files.readAllLines(out.resolve("rates-2026-10-14.csv"));
        assertEquals("pair,open,high,low,close,avg_mid,ticks,business_date", rows.get(0));
        assertEquals(3, rows.size());
        for (String row : rows.subList(1, rows.size())) assertTrue(row.endsWith(",2026-10-14"));
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
}
