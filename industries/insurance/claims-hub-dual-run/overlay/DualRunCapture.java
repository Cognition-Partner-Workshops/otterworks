package example.claimshub.golden;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Copied into a claims-hub-camel checkout by claims-hub-dual-run/dual_run.py and never committed there.
 * ByteComparison.of calls capture() first, so every Camel output a golden test compares is kept, keyed
 * by the SHA-256 of the golden it was compared with.
 */
final class DualRunCapture {

    private static final Path DIR = Path.of(System.getProperty("dualrun.capture.dir", "target/dual-run/capture"));
    private static final AtomicInteger SEQ = new AtomicInteger();

    private DualRunCapture() {
    }

    static synchronized void capture(byte[] expected, byte[] actual) {
        if (expected == null || actual == null) {
            return;
        }
        try {
            Files.createDirectories(DIR);
            String golden = sha256(expected);
            String name = String.format("%05d-%s.bin", SEQ.incrementAndGet(), golden.substring(0, 16));
            Files.write(DIR.resolve(name), actual);
            String line = golden + "\t" + sha256(actual) + "\t" + caller() + "\t" + name + "\n";
            Files.writeString(DIR.resolve("index.tsv"), line, StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (Exception e) {
            System.err.println("dual-run capture failed: " + e);
        }
    }

    private static String caller() {
        for (StackTraceElement frame : new Throwable().getStackTrace()) {
            String cls = frame.getClassName();
            if (cls.endsWith("DualRunCapture") || cls.endsWith("ByteComparison") || !cls.contains("Test")) {
                continue;
            }
            String simple = cls.substring(cls.lastIndexOf('.') + 1);
            int inner = simple.indexOf('$');
            return inner > 0 ? simple.substring(0, inner) : simple;
        }
        return "unknown";
    }

    private static String sha256(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
}
