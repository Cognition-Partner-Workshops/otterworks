package example.claimshub.payment;

import java.io.IOException;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.IntConsumer;

import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.spi.CamelEvent;
import org.apache.camel.support.EventNotifierSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.testcontainers.containers.Container;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;
import org.testcontainers.utility.MountableFile;

import com.icegreen.greenmail.util.GreenMail;
import com.icegreen.greenmail.util.ServerSetupTest;
import com.jcraft.jsch.JSch;
import com.jcraft.jsch.KeyPair;

import example.claimshub.ClaimsHubApplication;
import example.claimshub.golden.CorpusManifest;

/**
 * Harness for the ClaimPayment characterization tests. The three ports of the orchestration are real:
 * the ledger is PostgreSQL 16 (the WCF-SQL ports), the vendor is an SFTP server with public key
 * authentication and a pinned host key (sp_PaymentVendor_Remittance_SFTP), and operations is an SMTP
 * server (sp_Ops_PaymentHeld_SMTP, in-process GreenMail). The containers are started once per JVM and
 * removed by Testcontainers when the JVM exits.
 *
 * <p>The tests only rely on the orchestration's ports: {@code direct:claimPayment} receives a
 * Canonical_PaymentInstruction (PaymentIn), {@code direct:vendor.deliver} takes a positional remittance
 * file (Vendor.DeliverRemittance), the ledger is the table {@code ledger.claim_payment_entry}, and
 * every send to an {@code sftp:} or {@code smtp:} endpoint is observed as it leaves.
 */
@SpringBootTest(classes = ClaimsHubApplication.class, properties = {"camel.springboot.main-run-controller=false", "camel.component.direct.timeout=2000"})
@Import(ClaimPaymentTestSupport.Recording.class)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
public abstract class ClaimPaymentTestSupport {

    static final String VENDOR_USER = "thistlecombe-remit";
    static final String VENDOR_DIR = "inbound/thistlecombe";
    static final String VENDOR_PATH = "/home/" + VENDOR_USER + "/" + VENDOR_DIR;
    static final String OPS_MAILBOX = "claims-payments-ops@thistlecombe.example";
    static final String HUB_SENDER = "claims-hub@thistlecombe.example";
    static final long TEST_RETRY_DELAY_MS = 300;

    static final PostgreSQLContainer<?> LEDGER = new PostgreSQLContainer<>(
            DockerImageName.parse("mirror.gcr.io/library/postgres:16-alpine").asCompatibleSubstituteFor("postgres"))
            .withDatabaseName("claimsledger");
    static final GenericContainer<?> VENDOR;
    static final GreenMail OPS_SMTP = new GreenMail(ServerSetupTest.SMTP.dynamicPort());
    static final Path KEYS;

    static {
        try {
            KEYS = Files.createTempDirectory("claims-hub-vendor-keys");
            KeyPair pair = KeyPair.genKeyPair(new JSch(), KeyPair.RSA, 3072);
            pair.writePrivateKey(KEYS.resolve("id_rsa").toString());
            pair.writePublicKey(KEYS.resolve("id_rsa.pub").toString(), VENDOR_USER);
            pair.dispose();
        } catch (Exception e) {
            throw new IllegalStateException("cannot generate the vendor key pair", e);
        }
        VENDOR = new GenericContainer<>(DockerImageName.parse("mirror.gcr.io/atmoz/sftp:alpine"))
                .withCommand(VENDOR_USER + "::1001:100:inbound," + VENDOR_DIR + "," + VENDOR_DIR + "/tmp")
                .withCopyFileToContainer(MountableFile.forHostPath(KEYS.resolve("id_rsa.pub")), "/home/" + VENDOR_USER + "/.ssh/keys/id_rsa.pub")
                .withExposedPorts(22);
        LEDGER.start();
        VENDOR.start();
        OPS_SMTP.start();
        try {
            Container.ExecResult keys = VENDOR.execInContainer("sh", "-c", "cat /etc/ssh/ssh_host_*_key.pub");
            StringBuilder knownHosts = new StringBuilder();
            for (String line : keys.getStdout().split("\n")) {
                if (!line.isBlank()) {
                    String[] parts = line.trim().split("\\s+");
                    knownHosts.append("[").append(VENDOR.getHost()).append("]:").append(VENDOR.getMappedPort(22))
                            .append(' ').append(parts[0]).append(' ').append(parts[1]).append('\n');
                }
            }
            Files.writeString(KEYS.resolve("known_hosts"), knownHosts);
        } catch (Exception e) {
            throw new IllegalStateException("cannot pin the vendor host key", e);
        }
    }

    /** Wires the hub to the containers; {@code vendorReachable=false} points the hub at a port nobody listens on. */
    static void hubProperties(DynamicPropertyRegistry registry, boolean vendorReachable) {
        registry.add("spring.flyway.enabled", () -> "true");
        registry.add("spring.datasource.url", LEDGER::getJdbcUrl);
        registry.add("spring.datasource.username", LEDGER::getUsername);
        registry.add("spring.datasource.password", LEDGER::getPassword);
        registry.add("claims.payment.vendor.host", VENDOR::getHost);
        int port = vendorReachable ? VENDOR.getMappedPort(22) : closedPort();
        registry.add("claims.payment.vendor.port", () -> port);
        registry.add("claims.payment.vendor.private-key-file", () -> KEYS.resolve("id_rsa").toString());
        registry.add("claims.payment.vendor.known-hosts-file", () -> KEYS.resolve("known_hosts").toString());
        registry.add("claims.payment.vendor.retry-delay", () -> TEST_RETRY_DELAY_MS + "ms");
        registry.add("claims.payment.vendor.window.enabled", () -> "false");
        registry.add("claims.ops.smtp.host", () -> "127.0.0.1");
        registry.add("claims.ops.smtp.port", () -> OPS_SMTP.getSmtp().getPort());
        registry.add("claims.payment.inbox.enabled", () -> "false");
    }

    private static int closedPort() {
        try (ServerSocket socket = new ServerSocket(0)) {
            return socket.getLocalPort();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    /** One send as it left the hub, with the ledger as it stood at that moment. */
    public record Send(String uri, long nanos, String body, List<String> ledgerAtSend) {

        public String instructionId() {
            return body != null && body.startsWith("HDR") && body.length() >= 43 ? body.substring(27, 43).trim() : "";
        }
    }

    /** Records every exchange sent to an {@code sftp:} or {@code smtp:} endpoint, in order. */
    public static class SendRecorder extends EventNotifierSupport {

        private final JdbcTemplate jdbc;
        final List<Send> sends = new CopyOnWriteArrayList<>();
        volatile IntConsumer beforeSftpSend = n -> { };

        SendRecorder(JdbcTemplate jdbc) {
            this.jdbc = jdbc;
        }

        @Override
        public void notify(CamelEvent event) {
            if (event instanceof CamelEvent.ExchangeSendingEvent sending) {
                String uri = sending.getEndpoint().getEndpointUri();
                if (uri.startsWith("sftp:") || uri.startsWith("smtp:")) {
                    Exchange exchange = sending.getExchange();
                    if (uri.startsWith("sftp:")) {
                        beforeSftpSend.accept(sftpSends().size() + 1);
                    }
                    sends.add(new Send(uri, System.nanoTime(), exchange.getMessage().getBody(String.class), ledgerSnapshot()));
                }
            }
        }

        private List<String> ledgerSnapshot() {
            try {
                return jdbc.queryForList("select instruction_id || ':' || entry_type from ledger.claim_payment_entry order by entry_id", String.class);
            } catch (RuntimeException e) {
                return List.of("ledger unreadable: " + e.getMessage());
            }
        }

        List<Send> sftpSends() {
            return sends.stream().filter(s -> s.uri().startsWith("sftp:")).toList();
        }

        List<Send> smtpSends() {
            return sends.stream().filter(s -> s.uri().startsWith("smtp:")).toList();
        }

        void reset() {
            sends.clear();
            beforeSftpSend = n -> { };
        }
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class Recording {

        @Bean
        SendRecorder sendRecorder(JdbcTemplate jdbc) {
            return new SendRecorder(jdbc);
        }
    }

    @Autowired
    protected CamelContext camelContext;

    @Autowired
    protected ProducerTemplate producer;

    @Autowired
    protected JdbcTemplate jdbc;

    @Autowired
    protected SendRecorder recorder;

    @BeforeEach
    void cleanPorts() throws Exception {
        recorder.reset();
        clearVendorInbox();
        setVendorInboxWritable(true);
        OPS_SMTP.purgeEmailFromAllMailboxes();
        try {
            jdbc.execute("truncate ledger.claim_payment_entry restart identity");
        } catch (RuntimeException ignored) {
            // the ledger schema is the hub's to create; a test that needs it fails on its own query
        }
    }

    static Path paymentInput(String instructionId) {
        return CorpusManifest.fixtureDir().resolve("corpus/inputs/payment/" + instructionId + ".xml");
    }

    static Path ledgerPostGolden(String instructionId) {
        return CorpusManifest.fixtureDir().resolve("corpus/golden/ledger-post/" + instructionId + ".xml");
    }

    static Path remittanceGolden(String instructionId) {
        return CorpusManifest.fixtureDir().resolve("corpus/golden/vendor-remittance-ff/" + instructionId + ".txt");
    }

    static List<String> instructionIds() throws IOException {
        try (var files = Files.list(paymentInput("x").getParent())) {
            return files.map(p -> p.getFileName().toString()).filter(n -> n.endsWith(".xml"))
                    .map(n -> n.substring(0, n.length() - 4)).sorted().toList();
        }
    }

    /** Drops one payment instruction on the orchestration's activating receive, as the FILE port would. */
    protected Exchange pay(String instructionId) throws IOException {
        byte[] body = Files.readAllBytes(paymentInput(instructionId));
        return producer.request("direct:claimPayment", exchange -> {
            exchange.getIn().setBody(body);
            exchange.getIn().setHeader(Exchange.FILE_NAME, instructionId + ".xml");
        });
    }

    protected List<String> vendorFiles() throws Exception {
        Container.ExecResult ls = VENDOR.execInContainer("sh", "-c", "find " + VENDOR_PATH + " -maxdepth 1 -type f -exec basename {} \\; | sort");
        return Arrays.stream(ls.getStdout().split("\n")).filter(s -> !s.isBlank()).toList();
    }

    protected List<String> vendorTempFiles() throws Exception {
        Container.ExecResult ls = VENDOR.execInContainer("sh", "-c", "find " + VENDOR_PATH + "/tmp -type f -exec basename {} \\;");
        return Arrays.stream(ls.getStdout().split("\n")).filter(s -> !s.isBlank()).toList();
    }

    protected byte[] vendorFile(String name) {
        return VENDOR.copyFileFromContainer(VENDOR_PATH + "/" + name, in -> in.readAllBytes());
    }

    protected List<String> vendorFilesFor(String instructionId) throws Exception {
        List<String> matching = new ArrayList<>();
        for (String name : vendorFiles()) {
            String text = new String(vendorFile(name), StandardCharsets.US_ASCII);
            if (text.startsWith("HDR") && text.length() >= 43 && text.substring(27, 43).trim().equals(instructionId)) {
                matching.add(name);
            }
        }
        return matching;
    }

    protected void clearVendorInbox() throws Exception {
        VENDOR.execInContainer("sh", "-c", "find " + VENDOR_PATH + " -type f -delete");
    }

    protected void setVendorInboxWritable(boolean writable) {
        String mode = writable ? "755" : "555";
        try {
            VENDOR.execInContainer("chmod", mode, VENDOR_PATH, VENDOR_PATH + "/tmp");
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    protected List<Map<String, Object>> ledgerEntries(String instructionId) {
        return jdbc.queryForList("select entry_id, entry_type, document, indemnity_amount, expense_amount, salvage_credit, net_amount, line_count "
                + "from ledger.claim_payment_entry where instruction_id = ? order by entry_id", instructionId);
    }
}
