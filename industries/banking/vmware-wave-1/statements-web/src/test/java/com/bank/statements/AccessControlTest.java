package com.bank.statements;

import static org.junit.Assert.*;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.Principal;
import java.sql.Connection;
import java.sql.Statement;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Properties;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;
import org.h2.jdbcx.JdbcDataSource;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

public class AccessControlTest {
    private AccountsServlet accounts;
    private StatementServlet statement;
    private StatementDao dao;
    private Properties originalConfig;
    private final Map<String, Object> session = new HashMap<>();
    private int sessionAccesses;

    @Before
    public void setup() throws Exception {
        JdbcDataSource ds = new JdbcDataSource();
        ds.setURL("jdbc:h2:mem:access;DB_CLOSE_DELAY=-1");
        try (Connection c = ds.getConnection(); Statement s = c.createStatement()) {
            s.execute("DROP ALL OBJECTS");
            s.execute("CREATE TABLE accounts(account_id VARCHAR(20),holder VARCHAR(80))");
            s.execute("CREATE TABLE statement_lines(id INT,account_id VARCHAR(20),booked DATE,"
                + "description VARCHAR(60),amount DECIMAL(12,2),balance DECIMAL(12,2))");
            s.execute("INSERT INTO accounts VALUES('TEST0001','Synthetic A'),('TEST0002','Synthetic B')");
            s.execute("INSERT INTO statement_lines VALUES"
                + "(1,'TEST0001','2026-09-02','SALARY',100.00,100.00),"
                + "(2,'TEST0001','2026-09-03','CARD PAYMENT',-30.50,69.50),"
                + "(3,'TEST0002','2026-09-04','SYNTHETIC B',5.00,5.00)");
        }
        dao = new StatementDao(ds);
        Properties mappings = new Properties();
        mappings.setProperty("synthetic-a", "TEST0001");
        mappings.setProperty("synthetic-b", "TEST0002");
        mappings.setProperty("synthetic-joint", "TEST0002,TEST0001");
        StatementAccess access = new StatementAccess(mappings);
        accounts = new AccountsServlet();
        statement = new StatementServlet();
        inject(accounts, "dao", dao); inject(accounts, "access", access);
        inject(statement, "dao", dao); inject(statement, "access", access);
        Field props = AppConfig.class.getDeclaredField("props");
        props.setAccessible(true);
        originalConfig = (Properties) props.get(null);
        Properties config = new Properties();
        config.setProperty("bank.name", "Synthetic Bank");
        props.set(null, config);
    }

    @After
    public void restoreConfig() throws Exception {
        Field props = AppConfig.class.getDeclaredField("props");
        props.setAccessible(true); props.set(null, originalConfig);
    }

    @Test
    public void anonymousRequestsAreRejectedBeforeDatabaseOrSessionAccess() throws Exception {
        inject(accounts, "dao", null); inject(statement, "dao", null);
        Capture list = list(null);
        Capture detail = detail(null, "TEST0001");
        assertEquals(401, list.status); assertEquals(401, detail.status);
        assertEquals("", list.body()); assertEquals("", detail.body());
        assertEquals("no-store", list.headers.get("Cache-Control"));
        assertEquals("no-store", detail.headers.get("Cache-Control"));
        assertEquals(0, sessionAccesses);
    }

    @Test
    public void headersParametersAndSessionDoNotAuthenticateCaller() throws Exception {
        session.put("principal", "synthetic-a"); session.put("account", "TEST0001");
        assertEquals(401, list(null).status);
        assertEquals(401, detail(null, "TEST0001").status);
    }

    @Test
    public void unmappedPrincipalIsDeniedBeforeDatabaseOrSessionAccess() throws Exception {
        inject(accounts, "dao", null); inject(statement, "dao", null);
        assertEquals(403, list("unknown").status);
        assertEquals(403, detail("unknown", "TEST0001").status);
        assertEquals(0, sessionAccesses);
    }

    @Test
    public void absentMappingDeniesEvenAuthenticatedPrincipals() throws Exception {
        StatementAccess empty = StatementAccess.load(null);
        inject(accounts, "access", empty); inject(statement, "access", empty);
        assertEquals(403, list("synthetic-a").status);
        assertEquals(403, detail("synthetic-a", "TEST0001").status);
    }

    @Test
    public void listsOnlyOwnedAccountsInBothDirections() throws Exception {
        Capture a = list("synthetic-a"); Capture b = list("synthetic-b");
        assertEquals(200, a.status); assertEquals(200, b.status);
        assertTrue(a.body().contains(">Synthetic A<")); assertFalse(a.body().contains(">Synthetic B<"));
        assertTrue(b.body().contains(">Synthetic B<")); assertFalse(b.body().contains(">Synthetic A<"));
        assertFalse(a.body().contains("TEST0002")); assertFalse(b.body().contains("TEST0001"));
    }

    @Test
    public void otherAndNonexistentAccountsReturnSameNotFoundBeforeQuery() throws Exception {
        inject(statement, "dao", null);
        assertEquals(404, detail("synthetic-a", "TEST0002").status);
        assertEquals(404, detail("synthetic-b", "TEST0001").status);
        assertEquals(404, detail("synthetic-a", "TEST9999").status);
        assertEquals(0, sessionAccesses); assertTrue(session.isEmpty());
    }

    @Test
    public void malformedAccountStillReturnsBadRequestForAuthorizedCaller() throws Exception {
        for (String account : Arrays.asList(null, "bad", "TEST0001' OR 1=1", "../TEST0001")) {
            assertEquals(400, detail("synthetic-a", account).status);
        }
        assertEquals(0, sessionAccesses);
    }

    @Test
    public void ownedStatementsKeepOrderingValuesAndLastViewedNavigation() throws Exception {
        Capture response = detail("synthetic-a", "TEST0001");
        assertEquals(200, response.status);
        assertEquals("TEST0001", session.get("lastAccount"));
        assertTrue(response.body().contains("2 lines, net movement 69.50"));
        assertTrue(response.body().indexOf("SALARY") < response.body().indexOf("CARD PAYMENT"));
        assertTrue(list("synthetic-a").body().contains("id=\"last\""));
        assertEquals(new BigDecimal("69.50"), dao.lines("TEST0001", 2).get(1).balance);
        assertEquals(1, dao.lines("TEST0001", 1).size());
    }

    @Test
    public void authorizedBodiesMatchUnchangedSourceCharacterizationHashes() throws Exception {
        // SHA-256 of unchanged-source bodies with the same synthetic H2 fixture and bank name.
        assertEquals("c7e45563b0c1b7514c0a5e085a4e8b01dbed3cdfdab46e49af61c9f47ebb2a15",
            sha256(list("synthetic-joint").body()));
        assertEquals("451e1ccf4ef467c58cd7ee5b7555bbf74defbb731f489ea5e3f9f72a48e6125b",
            sha256(detail("synthetic-a", "TEST0001").body()));
        assertEquals("f096ac7c2eab31532b8ac121650abdcdce77f033938e65b3d31f0c678a82d955",
            sha256(detail("synthetic-b", "TEST0002").body()));
    }

    @Test
    public void readsServerSideMappingFile() throws Exception {
        Path path = Files.createTempFile("mod05-f875-statements-authz", ".properties");
        try {
            Files.write(path, "synthetic-a=TEST0001, TEST0002\n".getBytes(StandardCharsets.UTF_8));
            StatementAccess fileAccess = StatementAccess.load(path.toString());
            inject(accounts, "access", fileAccess);
            assertTrue(list("synthetic-a").body().contains(">Synthetic B<"));
            assertEquals(403, list("synthetic-b").status);
        } finally {
            Files.deleteIfExists(path);
        }
    }

    @Test(expected = java.io.IOException.class)
    public void unreadableConfiguredMappingFailsClosed() throws Exception {
        StatementAccess.load("/nonexistent/mod05-f875-statements-authz/access.properties");
    }

    @Test
    public void staleLastViewedAccountIsNotLeakedAcrossPrincipalChange() throws Exception {
        detail("synthetic-b", "TEST0002");
        Capture response = list("synthetic-a");
        assertFalse(response.body().contains("TEST0002"));
        assertFalse(response.body().contains("id=\"last\""));
    }

    @Test
    public void emptyGrantReturnsNoRowsAndBoundParametersCannotExpandQuery() throws Exception {
        assertTrue(dao.accounts(Collections.emptySet()).isEmpty());
        assertTrue(dao.accounts(Collections.singleton("TEST0001' OR 1=1 --")).isEmpty());
        assertEquals(Arrays.asList("TEST0001", "TEST0002"), Arrays.asList(
            dao.accounts(new HashSet<>(Arrays.asList("TEST0002", "TEST0001"))).keySet().toArray()));
    }

    @Test(expected = IllegalArgumentException.class)
    public void invalidMappingIsRejected() {
        Properties mappings = new Properties(); mappings.setProperty("synthetic-a", "TEST0001,bad");
        new StatementAccess(mappings);
    }

    @Test(expected = IllegalArgumentException.class)
    public void emptyGrantEntryIsRejected() {
        Properties mappings = new Properties(); mappings.setProperty("synthetic-a", "");
        new StatementAccess(mappings);
    }

    private Capture list(String name) throws Exception {
        Capture capture = new Capture(); accounts.doGet(request(name, null), capture.response()); return capture;
    }

    private Capture detail(String name, String account) throws Exception {
        Capture capture = new Capture(); statement.doGet(request(name, account), capture.response()); return capture;
    }

    private HttpServletRequest request(String name, String account) {
        HttpSession httpSession = (HttpSession) Proxy.newProxyInstance(HttpSession.class.getClassLoader(),
            new Class<?>[]{HttpSession.class}, (o, m, a) -> {
                if (m.getName().equals("getAttribute")) { return session.get(a[0]); }
                if (m.getName().equals("setAttribute")) { session.put((String) a[0], a[1]); }
                return null;
            });
        return (HttpServletRequest) Proxy.newProxyInstance(HttpServletRequest.class.getClassLoader(),
            new Class<?>[]{HttpServletRequest.class}, (o, m, a) -> {
                switch (m.getName()) {
                    case "getUserPrincipal": return name == null ? null : (Principal) () -> name;
                    case "getParameter": return "account".equals(a[0]) ? account : "synthetic-a";
                    case "getHeader": return "synthetic-a";
                    case "getSession": sessionAccesses++; return httpSession;
                    default: return null;
                }
            });
    }

    private static void inject(Object target, String name, Object value) throws Exception {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true); field.set(target, value);
    }

    private static String sha256(String body) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(body.getBytes(StandardCharsets.UTF_8));
        StringBuilder hex = new StringBuilder();
        for (byte value : digest) { hex.append(String.format("%02x", value & 0xff)); }
        return hex.toString();
    }

    private static class Capture {
        int status = 200;
        final StringWriter output = new StringWriter();
        final Map<String, String> headers = new HashMap<>();

        String body() { return output.toString(); }

        HttpServletResponse response() {
            return (HttpServletResponse) Proxy.newProxyInstance(HttpServletResponse.class.getClassLoader(),
                new Class<?>[]{HttpServletResponse.class}, (o, m, a) -> {
                    switch (m.getName()) {
                        case "getWriter": return new PrintWriter(output);
                        case "sendError": status = (int) a[0]; return null;
                        case "setHeader": headers.put((String) a[0], (String) a[1]); return null;
                        default: return null;
                    }
                });
        }
    }
}
