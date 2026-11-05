package com.bank.rates;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class RatesJobTest {

    private static final String DAY = "2026-10-14";
    private static final String CSV = "pair,open,high,low,close,avg_mid,ticks\n"
            + "EURGBP,0.860100,0.860100,0.860100,0.860100,0.860100,1\n"
            + "EURUSD,1.080100,1.081100,1.080100,1.081100,1.080600,2\n";

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

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
    public void publishesIdenticalCsvOnRerunWithoutLeavingStagingFiles() throws IOException {
        Path out = folder.getRoot().toPath().resolve("new-output");
        runJob(out);
        assertEquals(CSV, Files.readString(published(out)));
        Files.writeString(published(out), "stale output\n");
        runJob(out);
        assertEquals(CSV, Files.readString(published(out)));
        assertEquals(Arrays.asList("rates-" + DAY + ".csv"), entries(out));
    }

    @Test
    public void doesNotFollowPredictableStagingSymlink() throws IOException {
        Path out = folder.newFolder("out").toPath();
        Path victim = folder.newFile("synthetic-victim").toPath();
        Files.writeString(victim, "synthetic sentinel\n");
        Path link = out.resolve(".rates-" + DAY + ".tmp");
        Files.createSymbolicLink(link, victim);

        runJob(out);

        assertEquals("synthetic sentinel\n", Files.readString(victim));
        assertTrue(Files.isSymbolicLink(link));
        assertTrue(Files.isRegularFile(published(out), LinkOption.NOFOLLOW_LINKS));
        assertEquals(CSV, Files.readString(published(out)));
    }

    @Test
    public void leavesStalePredictableStagingFileUntouched() throws IOException {
        Path out = folder.newFolder("out").toPath();
        Path stale = out.resolve(".rates-" + DAY + ".tmp");
        Files.writeString(stale, "stale sentinel\n");

        runJob(out);

        assertEquals("stale sentinel\n", Files.readString(stale));
        assertEquals(CSV, Files.readString(published(out)));
        assertEquals(2, entries(out).size());
    }

    @Test
    public void atomicallyReplacesFinalSymlinkWithoutFollowingIt() throws IOException {
        Path out = folder.newFolder("out").toPath();
        Path victim = folder.newFile("synthetic-victim").toPath();
        Files.writeString(victim, "synthetic sentinel\n");
        Files.createSymbolicLink(published(out), victim);

        runJob(out);

        assertEquals("synthetic sentinel\n", Files.readString(victim));
        assertFalse(Files.isSymbolicLink(published(out)));
        assertEquals(CSV, Files.readString(published(out)));
    }

    @Test
    public void removesOwnStagingFileIfPublicationFails() throws IOException {
        Path out = folder.newFolder("out").toPath();
        Files.createDirectory(published(out));
        Files.writeString(published(out).resolve("keep"), "synthetic sentinel\n");

        assertThrows(IOException.class, () -> runJob(out));

        assertEquals("synthetic sentinel\n", Files.readString(published(out).resolve("keep")));
        assertEquals(Arrays.asList("rates-" + DAY + ".csv"), entries(out));
    }

    @Test
    public void retainsOrdinaryFileCreationPermissions() throws IOException {
        Path out = folder.newFolder("out").toPath();
        org.junit.Assume.assumeTrue(Files.getFileStore(out).supportsFileAttributeView("posix"));
        Path control = folder.newFile("permissions-control").toPath();

        runJob(out);

        assertEquals(Files.getPosixFilePermissions(control), Files.getPosixFilePermissions(published(out)));
    }

    @Test
    public void malformedTickStillFailsBeforePublishing() throws IOException {
        Path in = folder.newFolder("bad-input").toPath();
        Files.writeString(in.resolve("ticks-" + DAY + ".csv"), "2026-10-14T00:00:00Z,EURUSD,bad,1.0802\n");
        Path out = folder.getRoot().toPath().resolve("out");

        assertThrows(NumberFormatException.class,
                () -> RatesJob.main(new String[] {in.toString(), out.toString(), DAY}));

        assertFalse(Files.exists(out));
    }

    private void runJob(Path out) throws IOException {
        Path in = folder.getRoot().toPath().resolve("in");
        Files.createDirectories(in);
        Files.writeString(in.resolve("ticks-" + DAY + ".csv"), String.join("\n",
                "timestamp,pair,bid,ask",
                "2026-10-14T00:00:00Z,EURUSD,1.0800,1.0802",
                "2026-10-14T01:00:00Z,EURUSD,1.0810,1.0812",
                "2026-10-14T00:00:00Z,EURGBP,0.8600,0.8602"), StandardCharsets.UTF_8);
        RatesJob.main(new String[] {in.toString(), out.toString(), DAY});
    }

    private static Path published(Path out) {
        return out.resolve("rates-" + DAY + ".csv");
    }

    private static java.util.List<String> entries(Path dir) throws IOException {
        try (Stream<Path> paths = Files.list(dir)) {
            return paths.map(p -> p.getFileName().toString()).sorted().collect(Collectors.toList());
        }
    }
}
