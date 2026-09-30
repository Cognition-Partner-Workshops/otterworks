package com.otterworks.report.reconciliation;

import com.otterworks.report.archive.ArchiveDocument;
import com.otterworks.report.archive.ArchiveDocument.ArchiveVersion;
import com.otterworks.report.archive.ArchiveProperties;
import com.otterworks.report.archive.ArchiveStoreRegistry;
import com.otterworks.report.archive.SnowflakeArchiveStore;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assume.assumeTrue;

/**
 * SnowflakeArchiveStore and the Snowflake reconciliation SQL against a real Snowflake database.
 *
 * Skipped unless SNOWFLAKE_PAT and LDM_TEST_SNOWFLAKE_ACCOUNT are set; LDM_TEST_SNOWFLAKE_USER,
 * LDM_TEST_SNOWFLAKE_ROLE (default LDM_JOB_LDM_CI), LDM_TEST_SNOWFLAKE_WAREHOUSE (default LDM_WH) and
 * LDM_TEST_SNOWFLAKE_DATABASE (default OTTERWORKS_LDM_LDM_CI, the scratch database) name the rest. Every run seeds a
 * fresh namespace in ARCH.* and deletes it afterwards.
 */
public class SnowflakeLiveTest {

    private static final String DOC_ID = "5b0c1d6e-7f80-4a91-b2c3-d4e5f6a7b8c9";

    private JdbcTemplate jdbc;
    private String namespace;

    private static String env(String name, String fallback) {
        String v = System.getenv(name);
        return v == null || v.trim().isEmpty() ? fallback : v.trim();
    }

    @Before
    public void connect() {
        String account = env("LDM_TEST_SNOWFLAKE_ACCOUNT", "");
        String token = env("SNOWFLAKE_PAT", "");
        assumeTrue("SNOWFLAKE_PAT / LDM_TEST_SNOWFLAKE_ACCOUNT not set", !account.isEmpty() && !token.isEmpty());
        ArchiveProperties.Snowflake sf = new ArchiveProperties.Snowflake();
        sf.setAccount(account);
        sf.setUser(env("LDM_TEST_SNOWFLAKE_USER", ""));
        sf.setToken(token);
        sf.setRole(env("LDM_TEST_SNOWFLAKE_ROLE", "LDM_JOB_LDM_CI"));
        sf.setWarehouse(env("LDM_TEST_SNOWFLAKE_WAREHOUSE", "LDM_WH"));
        sf.setDatabase(env("LDM_TEST_SNOWFLAKE_DATABASE", "OTTERWORKS_LDM_LDM_CI"));
        jdbc = new JdbcTemplate(new ArchiveStoreRegistry.DataSourceFactory().snowflake(sf));
        namespace = "rs" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        String run = "run-" + namespace;
        jdbc.update("INSERT INTO ARCH.RETNPLCY (POLICY_CODE, POLICY_DESC, RETENTION_YEARS, SUCCESSOR_CODE, "
                + "ACTIVE_FLAG, DISPOSITION_ACTION, EFFECTIVE_TS, EFFECTIVE_TS_NANOS_TAIL, SOURCE_KEY, ROW_HASH, "
                + "NAMESPACE, MIGRATED_RUN_ID) SELECT 'FIN7', 'Finance seven years', 7, 'FIN7', 'Y', 'PURG', "
                + "'2019-01-01 00:00:00.000000'::TIMESTAMP_NTZ(6), 0, 'FIN7', SHA2_BINARY('FIN7', 256), ?, ?",
                namespace, run);
        for (int v = 1; v <= 2; v++) {
            jdbc.update("INSERT INTO ARCH.DOCARCH (ARCH_KEY, DOC_ID, VERSION_NO, RETENTION_CLASS, LAST_ACCESS_TS, "
                    + "LAST_ACCESS_TS_NANOS_TAIL, STORAGE_CHARGE, UNIT_RATE, OWNER_NAME, DISPOSITION_DT, "
                    + "LEGAL_HOLD_FLAG, CHECKSUM_ALG, CONTENT_SHA256, BYTE_SIZE, SOURCE_SYS, SOURCE_KEY, ROW_HASH, "
                    + "NAMESPACE, MIGRATED_RUN_ID) SELECT ?, ?, ?, 'FIN7', "
                    + "'2024-03-05 10:11:12.123456'::TIMESTAMP_NTZ(6), 789, 12.5, 0.25, 'Ada Owner', "
                    + "'2031-03-05'::DATE, 'N', 'SHA256  ', REPEAT('a', 64), 2048, 'DMS', ?, "
                    + "SHA2_BINARY(?, 256), ?, ?",
                    "DA" + namespace.substring(2) + "0" + v, DOC_ID, v, "DOC-" + v, "DOC-" + v, namespace, run);
        }
        jdbc.update("INSERT INTO ARCH.FILEAUD (AUDIT_KEY, ARCH_KEY, EVENT_TYPE, EVENT_TS, EVENT_TS_NANOS_TAIL, "
                + "ACTOR_ID, RETENTION_CLASS, DISPOSITION_CODE, CLIENT_IP, DETAIL_TEXT, SOURCE_KEY, ROW_HASH, "
                + "NAMESPACE, MIGRATED_RUN_ID) SELECT 'FA0000000000000001', ?, 'READ', "
                + "'2024-03-06 09:00:00.000001'::TIMESTAMP_NTZ(6), 0, 'U00000000001', 'FIN7', 'KP', '10.0.0.1', "
                + "'viewed', 'AUD-1', SHA2_BINARY('AUD-1', 256), ?, ?",
                "DA" + namespace.substring(2) + "01", namespace, run);
    }

    @After
    public void cleanUp() {
        if (jdbc == null) {
            return;
        }
        for (String table : new String[] {"ARCH.FILEAUD", "ARCH.DOCARCH", "ARCH.RETNPLCY"}) {
            jdbc.update("DELETE FROM " + table + " WHERE NAMESPACE = ?", namespace);
        }
    }

    @Test
    public void readsTheDocumentByArchKeyWithEventsAndPolicy() {
        SnowflakeArchiveStore store = new SnowflakeArchiveStore(jdbc, namespace);
        store.ping();

        Optional<ArchiveDocument> doc = store.findDocument("DA" + namespace.substring(2) + "02");

        assertTrue(doc.isPresent());
        assertEquals(DOC_ID, doc.get().getDocId());
        List<ArchiveVersion> versions = doc.get().getVersions();
        assertEquals(2, versions.size());
        assertEquals(1, versions.get(0).versionNo);
        assertEquals("FIN7", versions.get(0).policy.policyCode);
        assertEquals(1, versions.get(0).events.size());
        assertEquals("READ", versions.get(0).events.get(0).eventType);
        assertTrue(versions.get(1).events.isEmpty());
        assertEquals(doc.get().getDocId(), store.findDocument(DOC_ID).get().getDocId());
        assertFalse(store.findDocument("DA-UNKNOWN").isPresent());
    }

    @Test
    public void reconciliationViewsAnswerForTheNamespace() {
        String run = "run-" + namespace;
        assertTrue(jdbc.queryForList(ReconciliationRepository.SNOWFLAKE_RUNS_SQL, namespace).isEmpty());
        assertTrue(jdbc.queryForList(ReconciliationRepository.SNOWFLAKE_RUN_SQL, namespace, run).isEmpty());
        assertTrue(jdbc.queryForList(ReconciliationRepository.SNOWFLAKE_TABLES_SQL, namespace, run).isEmpty());
        assertTrue(jdbc.queryForList(ReconciliationRepository.SNOWFLAKE_FAILURES_SQL, namespace, run).isEmpty());
        List<Map<String, Object>> totals =
                jdbc.queryForList(ReconciliationRepository.SNOWFLAKE_CLASS_TOTALS_SQL, namespace, run);
        assertEquals(1, totals.size());
        assertEquals("FIN7", totals.get(0).get("class_code"));
        assertEquals(2L, ((Number) totals.get(0).get("row_count")).longValue());
    }
}
