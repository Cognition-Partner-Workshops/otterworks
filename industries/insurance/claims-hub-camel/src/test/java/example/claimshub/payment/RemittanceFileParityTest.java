package example.claimshub.payment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.fail;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

import org.apache.camel.Exchange;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.DynamicContainer;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;

import example.claimshub.golden.ByteComparison;

/**
 * All 14 payment instructions through {@code direct:claimPayment} with the vendor up. Per instruction:
 * the ledger holds exactly one post and the vendor inbox exactly one file for it (never one without the
 * other); the file has HDR, PAY and TRL records of the schema's widths, CRLF after each, and a trailer
 * that agrees with its body; and the file is byte-identical to corpus/golden/vendor-remittance-ff. A
 * file that is not identical stays red, with the first differing field and the reason named in the
 * report ({@code target/golden-report/VendorRemittanceFile.md}).
 */
class RemittanceFileParityTest extends ReachableVendorTestSupport {

    record Row(String instruction, int goldenBytes, int camelBytes, boolean identical, String ledgerNet, String fileNet, String cause) {
    }

    private final Map<String, Row> rows = new LinkedHashMap<>();
    private final Map<String, Exchange> results = new LinkedHashMap<>();

    @TestFactory
    Stream<DynamicContainer> fourteenInstructions() throws Exception {
        List<String> ids = instructionIds();
        assertThat(ids).hasSize(14);
        for (String id : ids) {
            results.put(id, pay(id));
        }
        List<DynamicContainer> containers = new ArrayList<>();
        containers.add(DynamicContainer.dynamicContainer("ledger and vendor inbox", Stream.of(
                DynamicTest.dynamicTest("no file without a post", this::noFileWithoutAPost))));
        for (String id : ids) {
            containers.add(DynamicContainer.dynamicContainer(id, Stream.of(
                    DynamicTest.dynamicTest("one post and one file", () -> onePostAndOneFile(id)),
                    DynamicTest.dynamicTest("layout and trailer", () -> layout(id)),
                    DynamicTest.dynamicTest("byte-identical to golden", () -> parity(id)),
                    DynamicTest.dynamicTest("ledger and file agree to the cent", () -> ledgerAgreesWithFile(id)))));
        }
        return containers.stream();
    }

    private void noFileWithoutAPost() throws Exception {
        assertThat(vendorFiles()).as("files in the vendor inbox").isNotEmpty();
        for (String name : vendorFiles()) {
            String text = new String(vendorFile(name), StandardCharsets.US_ASCII);
            assertThat(text).as(name).startsWith("HDR");
            String instruction = text.substring(27, 43).trim();
            assertThat(ledgerEntries(instruction)).as("ledger entries for the file %s", name)
                    .extracting(e -> e.get("entry_type")).containsExactly("POST");
        }
    }

    private void onePostAndOneFile(String id) throws Exception {
        assertThat(results.get(id).getException()).isNull();
        assertThat(ledgerEntries(id)).extracting(e -> e.get("entry_type")).containsExactly("POST");
        assertThat(vendorFilesFor(id)).hasSize(1);
    }

    private String camelFile(String id) throws Exception {
        List<String> files = vendorFilesFor(id);
        if (files.size() != 1) {
            fail("expected one vendor file for " + id + ", found " + files);
        }
        return new String(vendorFile(files.get(0)), StandardCharsets.US_ASCII);
    }

    private void layout(String id) throws Exception {
        String file = camelFile(id);
        Map<String, RemittanceSchema.Record> schema = RemittanceSchema.load();
        assertThat(file).endsWith("\r\n");
        assertThat(file.replace("\r\n", "")).doesNotContain("\r").doesNotContain("\n");
        assertThat(file.chars().allMatch(c -> c >= 0x20 && c < 0x7f || c == '\r' || c == '\n')).as("US-ASCII printable").isTrue();
        String[] records = file.substring(0, file.length() - 2).split("\r\n", -1);
        assertThat(records.length).isGreaterThanOrEqualTo(3);
        for (int i = 0; i < records.length; i++) {
            String tag = i == 0 ? "HDR" : i == records.length - 1 ? "TRL" : "PAY";
            String record = records[i];
            RemittanceSchema.Record layout = schema.get(tag);
            assertThat(record).as("record %d", i + 1).startsWith(tag).hasSize(layout.length());
            for (RemittanceSchema.Field field : layout.fields()) {
                String value = field.slice(record);
                if (field.right() && field.pad() == '0') {
                    assertThat(value).as("%s.%s in record %d", tag, field.name(), i + 1).matches("[0-9]{" + field.length() + "}");
                }
            }
        }
        assertThat(TrailerTotalsReference.check(file)).as("trailer against body").isNull();
        long pays = java.util.Arrays.stream(records).filter(r -> r.startsWith("PAY")).count();
        assertThat(Long.parseLong(records[records.length - 1].substring(3, 9))).isEqualTo(pays);
    }

    private void parity(String id) throws Exception {
        byte[] golden = Files.readAllBytes(remittanceGolden(id));
        byte[] actual;
        try {
            actual = camelFile(id).getBytes(StandardCharsets.US_ASCII);
        } catch (AssertionError e) {
            Exception refused = results.get(id).getException();
            String legacy = TrailerTotalsReference.legacyVerdict(new String(golden, StandardCharsets.US_ASCII));
            String why = (refused == null ? "no vendor file" : "no vendor file: " + refused.getMessage())
                    + "; ledger " + ledgerEntries(id).stream().map(entry -> String.valueOf(entry.get("entry_type"))).toList();
            if (legacy != null) {
                why += "; the golden itself fails the legacy TrailerTotalsComponent (" + legacy + ")";
            }
            rows.put(id, new Row(id, golden.length, 0, false, ledgerNet(id), "", why));
            throw e;
        }
        ByteComparison comparison = ByteComparison.of(golden, actual);
        String cause = comparison.identical() ? "" : cause(new String(golden, StandardCharsets.US_ASCII), new String(actual, StandardCharsets.US_ASCII), comparison);
        rows.put(id, new Row(id, golden.length, actual.length, comparison.identical(), ledgerNet(id), fileNet(new String(actual, StandardCharsets.US_ASCII)), cause));
        if (!comparison.identical()) {
            fail(id + ": " + cause);
        }
    }

    private void ledgerAgreesWithFile(String id) throws Exception {
        String file = camelFile(id);
        BigDecimal ledger = new BigDecimal(ledgerNet(id));
        BigDecimal net = new BigDecimal(fileNet(file));
        if (ledger.compareTo(net) != 0) {
            String cause = "ledger net " + ledger.toPlainString() + " but file net " + net.toPlainString()
                    + ": Payment_to_LedgerPost rounds the summed line amounts once, Payment_to_VendorRemittance rounds every line to"
                    + " cents before summing; the ledger keeps the legacy post, and which amount is paid is a claims finance decision (ESTATE.md)";
            Row row = rows.get(id);
            if (row != null) {
                rows.put(id, new Row(row.instruction(), row.goldenBytes(), row.camelBytes(), row.identical(), row.ledgerNet(), row.fileNet(),
                        row.cause().isEmpty() ? cause : row.cause() + "; " + cause));
            }
            fail(id + ": " + cause);
        }
    }

    /** Names the first differing field and says whether the legacy pipeline could have sent the golden at all. */
    static String cause(String golden, String actual, ByteComparison comparison) {
        Map<String, RemittanceSchema.Record> schema = RemittanceSchema.load();
        String[] g = golden.split("\r\n");
        String[] a = actual.split("\r\n");
        String where = comparison.cause();
        for (int i = 0; i < Math.min(g.length, a.length); i++) {
            if (!g[i].equals(a[i])) {
                RemittanceSchema.Record layout = schema.get(g[i].length() >= 3 ? g[i].substring(0, 3) : "");
                if (layout != null) {
                    for (RemittanceSchema.Field field : layout.fields()) {
                        if (field.offset() + field.length() <= Math.min(g[i].length(), a[i].length()) && !field.slice(g[i]).equals(field.slice(a[i]))) {
                            where = "record " + (i + 1) + " " + layout.tag() + "." + field.name() + ": golden `" + field.slice(g[i]) + "`, camel `" + field.slice(a[i]) + "`";
                            break;
                        }
                    }
                }
                break;
            }
        }
        String legacy = TrailerTotalsReference.legacyVerdict(golden);
        if (legacy != null && golden.contains("E")) {
            return where + "; the golden carries Saxon's exponent form of round() (XPath 2.0 double-to-string), which the legacy "
                    + "TrailerTotalsComponent cannot parse (" + legacy + "), so the legacy send pipeline would have suspended this golden";
        }
        return where;
    }

    private String ledgerNet(String id) {
        List<Map<String, Object>> entries = ledgerEntries(id);
        return entries.isEmpty() ? "" : ((BigDecimal) entries.get(0).get("net_amount")).toPlainString();
    }

    static String fileNet(String file) {
        long debit = 0;
        long credit = 0;
        for (String record : file.split("\r\n")) {
            if (record.startsWith("PAY") && record.length() >= 70) {
                long cents = Long.parseLong(record.substring(57, 69));
                if (record.charAt(69) == 'C') {
                    credit += cents;
                } else {
                    debit += cents;
                }
            }
        }
        return BigDecimal.valueOf(debit - credit, 2).toPlainString();
    }

    @AfterAll
    void writeReport() throws Exception {
        Path dir = Path.of("target", "golden-report");
        Files.createDirectories(dir);
        StringBuilder md = new StringBuilder();
        md.append("| Instruction | Golden bytes | Camel bytes | Byte-identical | Ledger net | File net (D-C) | Ledger - file | Verdict | Cause |\n");
        md.append("| --- | ---: | ---: | --- | ---: | ---: | ---: | --- | --- |\n");
        int identical = 0;
        int red = 0;
        BigDecimal ledgerTotal = BigDecimal.ZERO;
        BigDecimal fileTotal = BigDecimal.ZERO;
        for (Row row : rows.values()) {
            String diff = "";
            if (!row.ledgerNet().isEmpty() && !row.fileNet().isEmpty()) {
                BigDecimal l = new BigDecimal(row.ledgerNet());
                BigDecimal f = new BigDecimal(row.fileNet());
                ledgerTotal = ledgerTotal.add(l);
                fileTotal = fileTotal.add(f);
                diff = l.subtract(f).toPlainString();
            }
            boolean green = row.identical() && !diff.isEmpty() && new BigDecimal(diff).signum() == 0;
            if (!green) {
                red++;
            }
            md.append("| ").append(row.instruction()).append(" | ").append(row.goldenBytes()).append(" | ").append(row.camelBytes())
                    .append(" | ").append(row.identical() ? "yes" : "**no**").append(" | ").append(row.ledgerNet()).append(" | ")
                    .append(row.fileNet()).append(" | ").append(diff).append(" | ").append(green ? "green" : "**red**").append(" | ").append(row.cause().replace("|", "\\|")).append(" |\n");
            if (row.identical()) {
                identical++;
            }
        }
        md.append("| **Total** | | | **").append(identical).append(" of ").append(rows.size()).append(" identical** | ")
                .append(ledgerTotal.toPlainString()).append(" | ").append(fileTotal.toPlainString()).append(" | ")
                .append(ledgerTotal.subtract(fileTotal).toPlainString()).append(" | ").append(red).append(" red | |\n");
        Files.writeString(dir.resolve("VendorRemittanceFile.md"), md.toString(), StandardCharsets.UTF_8);
    }
}
