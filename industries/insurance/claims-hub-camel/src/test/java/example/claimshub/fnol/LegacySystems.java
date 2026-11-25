package example.claimshub.fnol;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.LocalDate;
import java.util.List;
import java.util.stream.Stream;

import javax.xml.parsers.DocumentBuilderFactory;

import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import example.claimshub.golden.CorpusManifest;

/**
 * One PostgreSQL 16 container for the whole test run, standing in for the policy admin and claims system
 * databases behind the WCF-SQL ports. Policies are seeded from {@code corpus/stubs/policy}, the answers the
 * BizTalk port gives, plus one later version that only an as-of-report-date lookup would find.
 */
public final class LegacySystems {

    /** POL-HOME-48163 backs CLM-2026-100409 (loss 2026-09-15, reported 2026-09-29); it is cancelled in between. */
    public static final String AS_OF_POLICY = "POL-HOME-48163";
    public static final LocalDate AS_OF_CANCELLED_FROM = LocalDate.parse("2026-09-20");

    private static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
            DockerImageName.parse(System.getProperty("claims.postgres.image", "postgres:16-alpine"))
                    .asCompatibleSubstituteFor("postgres"))
            .withDatabaseName("claimshub").withUsername("claimshub").withPassword("claimshub");

    private static boolean seeded;

    private LegacySystems() {
    }

    public static synchronized PostgreSQLContainer<?> postgres() {
        if (!POSTGRES.isRunning()) {
            POSTGRES.start();
        }
        if (!seeded) {
            try (Connection c = connect(); Statement s = c.createStatement()) {
                s.execute(Files.readString(Path.of("src/test/resources/db/wcf-sql-stand-in.sql")));
                seedPolicies(c);
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            } catch (Exception e) {
                throw new IllegalStateException("cannot seed the WCF-SQL stand-in", e);
            }
            seeded = true;
        }
        return POSTGRES;
    }

    public static Connection connect() throws SQLException {
        return DriverManager.getConnection(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
    }

    public static void clearClaims() {
        try (Connection c = connect(); Statement s = c.createStatement()) {
            s.execute("truncate claim");
        } catch (SQLException e) {
            throw new IllegalStateException(e);
        }
    }

    public record ClaimRow(String claimNumber, String policyStatus, BigDecimal estimatedAmount, BigDecimal netExposure,
            boolean inForceAtLoss, String agencyId, String triageOutcome) {
    }

    public static List<ClaimRow> claims() {
        try (Connection c = connect(); Statement s = c.createStatement();
                var rs = s.executeQuery("select claim_number, policy_status, estimated_amount, net_exposure, in_force_at_loss, agency_id, triage_outcome from claim order by claim_number")) {
            var rows = new java.util.ArrayList<ClaimRow>();
            while (rs.next()) {
                rows.add(new ClaimRow(rs.getString(1), rs.getString(2), rs.getBigDecimal(3), rs.getBigDecimal(4),
                        rs.getBoolean(5), rs.getString(6), rs.getString(7)));
            }
            return rows;
        } catch (SQLException e) {
            throw new IllegalStateException(e);
        }
    }

    private static void seedPolicies(Connection c) throws Exception {
        Path stubs = CorpusManifest.fixtureDir().resolve("corpus/stubs/policy");
        List<Path> files;
        try (Stream<Path> list = Files.list(stubs)) {
            files = list.filter(p -> p.toString().endsWith(".xml")).sorted().toList();
        }
        var dbf = DocumentBuilderFactory.newInstance();
        dbf.setNamespaceAware(true);
        try (PreparedStatement version = c.prepareStatement(
                "insert into policy_version (policy_number, valid_from, valid_to, status_cd, lob_cd, effective_dt, expiration_dt, deductible_amt, coverage_limit_amt, insured_party_id) values (?, ?::date, ?::date, ?, ?, ?::date, ?::date, ?, ?, ?)");
                PreparedStatement coverage = c.prepareStatement(
                        "insert into policy_coverage (policy_number, valid_from, seq, coverage_cd, limit_amt) values (?, ?::date, ?, ?, ?)")) {
            for (Path file : files) {
                Document doc = dbf.newDocumentBuilder().parse(new java.io.ByteArrayInputStream(Files.readString(file, StandardCharsets.UTF_8).getBytes(StandardCharsets.UTF_8)));
                Element rs = doc.getDocumentElement();
                String number = text(rs, "PolicyNumber");
                boolean asOfCase = AS_OF_POLICY.equals(number);
                addVersion(version, coverage, rs, "-infinity", asOfCase ? AS_OF_CANCELLED_FROM.toString() : "infinity", text(rs, "PolicyStatusCd"));
                if (asOfCase) {
                    addVersion(version, coverage, rs, AS_OF_CANCELLED_FROM.toString(), "infinity", "Cancelled");
                }
            }
        }
    }

    private static void addVersion(PreparedStatement version, PreparedStatement coverage, Element rs, String from, String to, String status) throws SQLException {
        String number = text(rs, "PolicyNumber");
        version.setString(1, number);
        version.setString(2, from);
        version.setString(3, to);
        version.setString(4, status);
        version.setString(5, text(rs, "LOBCd"));
        version.setString(6, text(rs, "EffectiveDt"));
        version.setString(7, text(rs, "ExpirationDt"));
        version.setBigDecimal(8, new BigDecimal(text(rs, "DeductibleAmt")));
        version.setBigDecimal(9, new BigDecimal(text(rs, "CoverageLimitAmt")));
        version.setString(10, text(rs, "InsuredPartyId"));
        version.executeUpdate();
        NodeList coverages = rs.getElementsByTagName("Coverage");
        for (int i = 0; i < coverages.getLength(); i++) {
            Element cov = (Element) coverages.item(i);
            coverage.setString(1, number);
            coverage.setString(2, from);
            coverage.setInt(3, i + 1);
            coverage.setString(4, text(cov, "CoverageCd"));
            coverage.setBigDecimal(5, new BigDecimal(text(cov, "LimitAmt")));
            coverage.executeUpdate();
        }
    }

    static String text(Element parent, String child) {
        NodeList nodes = parent.getElementsByTagName(child);
        if (nodes.getLength() == 0) {
            throw new IllegalArgumentException("no " + child + " under " + parent.getTagName());
        }
        return nodes.item(0).getTextContent().trim();
    }
}
