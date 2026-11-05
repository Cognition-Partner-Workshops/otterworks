package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;

import java.io.InputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.cert.X509Certificate;
import java.util.Properties;
import java.util.concurrent.TimeUnit;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;

/** Uses only throwaway keystores generated per test; no real keystore or password. */
class KeystorePasswordTest {

    private static final String PUBLIC_DEFAULT = "changeit";
    private static final String SYNTHETIC = "synthetic-test-only-7f3a";

    @TempDir
    Path tmp;

    @Test
    void passwordPropertyHasNoFallback() throws Exception {
        Properties p = new Properties();
        try (InputStream in = getClass().getResourceAsStream("/application.properties")) {
            p.load(in);
        }
        assertEquals("${KEYSTORE_PASSWORD}", p.getProperty("server.ssl.key-store-password"));
    }

    @Test
    void refusesToStartWithoutKeystorePassword() throws Exception {
        Path ks = keystore(PUBLIC_DEFAULT);
        assertThrows(Exception.class, () -> start(ks, null).close());
    }

    @Test
    void refusesToStartWithWrongKeystorePassword() throws Exception {
        Path ks = keystore(SYNTHETIC);
        assertThrows(Exception.class, () -> start(ks, "not-the-password").close());
    }

    @Test
    void servesHttpsWithExplicitKeystorePassword() throws Exception {
        Path ks = keystore(SYNTHETIC);
        try (ConfigurableApplicationContext ctx = start(ks, SYNTHETIC)) {
            int port = ((WebServerApplicationContext) ctx).getWebServer().getPort();
            HttpsURLConnection c = (HttpsURLConnection) new URL("https://localhost:" + port + "/documents/HG611000001").openConnection();
            c.setSSLSocketFactory(trustAll().getSocketFactory());
            c.setHostnameVerifier((h, s) -> true);
            assertEquals(200, c.getResponseCode());
            try (InputStream in = c.getInputStream()) {
                assertEquals("[]", new String(in.readAllBytes(), StandardCharsets.UTF_8));
            }
        }
    }

    private ConfigurableApplicationContext start(Path ks, String password) {
        SpringApplication app = new SpringApplication(KycDocsApplication.class);
        java.util.List<String> args = new java.util.ArrayList<>(java.util.List.of(
                "--server.port=0",
                "--server.ssl.key-store=" + ks,
                "--kyc.upload-dir=" + tmp.resolve("uploads"),
                "--logging.file.name=" + tmp.resolve("kyc-docs.log")));
        if (password != null) {
            args.add("--KEYSTORE_PASSWORD=" + password);
        }
        return app.run(args.toArray(new String[0]));
    }

    private Path keystore(String password) throws Exception {
        Path ks = tmp.resolve("keystore-" + System.nanoTime() + ".p12");
        String keytool = Paths.get(System.getProperty("java.home"), "bin", "keytool").toString();
        Process p = new ProcessBuilder(keytool, "-genkeypair", "-alias", "kyc", "-keyalg", "RSA", "-keysize", "2048",
                "-validity", "1", "-dname", "CN=localhost", "-storetype", "PKCS12", "-keystore", ks.toString(),
                "-storepass", password, "-keypass", password).inheritIO().start();
        assertTrue(p.waitFor(60, TimeUnit.SECONDS));
        assertEquals(0, p.exitValue());
        return ks;
    }

    private static SSLContext trustAll() throws Exception {
        SSLContext ctx = SSLContext.getInstance("TLS");
        ctx.init(null, new TrustManager[] {new X509TrustManager() {
            public void checkClientTrusted(X509Certificate[] c, String a) { }
            public void checkServerTrusted(X509Certificate[] c, String a) { }
            public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
        }}, null);
        return ctx;
    }
}
