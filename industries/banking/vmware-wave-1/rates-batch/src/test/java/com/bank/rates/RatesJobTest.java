package com.bank.rates;

import static org.junit.Assert.assertEquals;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import org.junit.Test;

public class RatesJobTest {

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
    public void skipsMalformedRowsAndKeepsTheRestOfTheDay() {
        List<String> rejected = new ArrayList<>();
        Map<String, RatesJob.Daily> r = RatesJob.aggregate(Arrays.asList(
                "timestamp,pair,bid,ask",
                "2026-10-14T00:00:00Z,EURUSD,1.0800,1.0802",
                "2026-10-14T00:30:00Z,EURUSD,1.0805",
                "2026-10-14T00:45:00Z,EURUSD,N/A,1.0810",
                null,
                "2026-10-14T00:55:00Z,EUR\uFFFDUSD,1.0801,1.0803",
                "2026-10-14T00:58:00Z,EUR-USD,1.0801,1.0803",
                "2026-10-14T00:59:00Z,USDJPY,150.00,150.02,src=\uFFFD",
                "",
                "2026-10-14T01:00:00Z,EURUSD,1.0810,1.0812",
                "2026-10-14T02:00:00Z,EURUSD,1.0790,1.0792",
                "2026-10-14T00:00:00Z,EURGBP,0.8600,0.8602"), rejected);
        assertEquals(3, r.size());
        assertEquals("EURUSD,1.080100,1.081100,1.079100,1.079100,1.080100,3", r.get("EURUSD").csv());
        assertEquals("EURGBP,0.860100,0.860100,0.860100,0.860100,0.860100,1", r.get("EURGBP").csv());
        assertEquals("USDJPY,150.010000,150.010000,150.010000,150.010000,150.010000,1", r.get("USDJPY").csv());
        assertEquals(Arrays.asList(
                "line 3: expected 4 fields, found 3",
                "line 4: bid or ask is not a number",
                "line 5: contains bytes that are not UTF-8",
                "line 6: pair is not six letters A-Z",
                "line 7: pair is not six letters A-Z"), rejected);
    }

    @Test
    public void readLinesRejectsOnlyRowsWithInvalidUtf8() throws Exception {
        ByteArrayOutputStream file = new ByteArrayOutputStream();
        file.write("timestamp,pair,bid,ask\r\n2026-10-14T00:00:00".getBytes(StandardCharsets.UTF_8));
        file.write(new byte[] {(byte) 0xc3, (byte) 0x28});
        file.write(",EURUSD,1.0800,1.0802\r2026-10-14T00:10:00Z,EUR".getBytes(StandardCharsets.UTF_8));
        file.write(new byte[] {(byte) 0xff, (byte) 0xfe});
        file.write("USD,1.0801,1.0803\n2026-10-14T00:20:00Z,EURUSD,1.0801,1.0803,note=\uFFFD caf\u00e9\n2026-10-14T00:30:00Z,EURUSD,1.0801,1.0803"
                .getBytes(StandardCharsets.UTF_8));

        assertEquals(Arrays.asList("timestamp,pair,bid,ask", null, null,
                "2026-10-14T00:20:00Z,EURUSD,1.0801,1.0803,note=\uFFFD caf\u00e9",
                "2026-10-14T00:30:00Z,EURUSD,1.0801,1.0803"), RatesJob.readLines(file.toByteArray()));
    }

    @Test
    public void mainWritesTheDayWhenOneRowHasUndecodableBytes() throws Exception {
        Path in = Files.createTempDirectory("rates-in");
        Path out = Files.createTempDirectory("rates-out");
        ByteArrayOutputStream file = new ByteArrayOutputStream();
        file.write("timestamp,pair,bid,ask\n2026-10-14T00:00:00Z,EURUSD,1.0800,1.0802\n2026-10-14T00:10:00Z,EUR"
                .getBytes(StandardCharsets.UTF_8));
        file.write(new byte[] {(byte) 0xff, (byte) 0xfe});
        file.write("USD,1.0801,1.0803\n2026-10-14T00:20:00".getBytes(StandardCharsets.UTF_8));
        file.write(new byte[] {(byte) 0xed, (byte) 0xa0, (byte) 0x80});
        file.write(",EURUSD,1.0801,1.0803\n2026-10-14T00:30:00Z,EURUSD,1.0810,1.0812,src=\uFFFD\n".getBytes(StandardCharsets.UTF_8));
        file.write("2026-10-14T01:00:00Z,EURUSD,1.0810,1.0812\n".getBytes(StandardCharsets.UTF_8));
        Files.write(in.resolve("ticks-2026-10-14.csv"), file.toByteArray());

        RatesJob.main(new String[] {in.toString(), out.toString(), "2026-10-14"});

        assertEquals(Arrays.asList("pair,open,high,low,close,avg_mid,ticks",
                        "EURUSD,1.080100,1.081100,1.080100,1.081100,1.080767,3"),
                Files.readAllLines(out.resolve("rates-2026-10-14.csv"), StandardCharsets.UTF_8));
    }
}
