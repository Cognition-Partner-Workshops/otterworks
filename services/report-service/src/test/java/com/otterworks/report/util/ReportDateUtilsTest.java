package com.otterworks.report.util;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;

public class ReportDateUtilsTest {

    private static final Date NOV_10_2026 = new Date(1794313800000L); // 2026-11-10T12:30:00Z

    private static String legacy(String pattern, Date date) {
        SimpleDateFormat format = new SimpleDateFormat(pattern);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(date);
    }

    private static String[] underLocale(Locale locale) throws Exception {
        Locale previous = Locale.getDefault();
        Locale.setDefault(locale);
        try {
            AtomicReference<String[]> out = new AtomicReference<>();
            Thread thread = new Thread(() -> out.set(new String[] {
                ReportDateUtils.toDisplayString(NOV_10_2026),
                ReportDateUtils.toFileNameString(NOV_10_2026),
                legacy("MMM dd, yyyy HH:mm", NOV_10_2026),
                legacy("yyyyMMdd_HHmmss", NOV_10_2026),
            }));
            thread.start();
            thread.join();
            return out.get();
        } finally {
            Locale.setDefault(previous);
        }
    }

    @Test
    public void thaiLocaleKeepsBuddhistCalendar() throws Exception {
        String[] r = underLocale(new Locale("th", "TH"));
        assertEquals(r[2], r[0]);
        assertEquals(r[3], r[1]);
        assertTrue(r[0], r[0].contains("2569"));
    }

    @Test
    public void arabicLocaleMatchesLegacyFormatter() throws Exception {
        String[] r = underLocale(new Locale("ar", "SA"));
        assertEquals(r[2], r[0]);
        assertEquals(r[3], r[1]);
    }

    @Test
    public void formattingIsThreadSafe() throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(8);
        try {
            List<Future<Boolean>> results = new ArrayList<>();
            for (int i = 0; i < 2000; i++) {
                Date date = new Date(NOV_10_2026.getTime() + i * 86_400_000L);
                String expected = legacy("yyyyMMdd_HHmmss", date);
                Callable<Boolean> task = () -> expected.equals(ReportDateUtils.toFileNameString(date));
                results.add(pool.submit(task));
            }
            for (Future<Boolean> result : results) {
                assertEquals(true, result.get());
            }
        } finally {
            pool.shutdown();
        }
    }
}
