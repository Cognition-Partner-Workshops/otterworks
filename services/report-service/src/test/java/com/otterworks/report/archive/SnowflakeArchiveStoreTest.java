package com.otterworks.report.archive;

import com.otterworks.report.archive.ArchiveDocument.ArchiveEvent;
import com.otterworks.report.archive.ArchiveDocument.ArchiveVersion;
import com.otterworks.report.archive.ArchiveDocument.RetentionPolicy;
import org.junit.Test;
import org.mockito.ArgumentMatchers;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;

import java.util.Arrays;
import java.util.Collections;
import java.util.Optional;
import java.util.Properties;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/** SnowflakeArchiveStore against a mocked JdbcTemplate: SQL, bind values and assembly. */
public class SnowflakeArchiveStoreTest {

    private static final String NS = "s30-after";

    private static ArchiveVersion version(String archKey, int no) {
        ArchiveVersion v = new ArchiveVersion();
        v.raw.archKey = archKey;
        v.raw.docId = "0f8fad5b-d9cb-469f-a165-70867728950e";
        v.archKey = archKey;
        v.versionNo = no;
        v.retentionClass = "FIN7";
        return v;
    }

    private static ArchiveEvent event(String key, String archKey) {
        ArchiveEvent e = new ArchiveEvent();
        e.raw.auditKey = key;
        e.auditKey = key;
        e.archKey = archKey;
        return e;
    }

    @Test
    public void looksUpTheDocumentByArchKeyScopedToTheNamespace() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.query(eq(SnowflakeArchiveStore.VERSIONS_SQL), ArgumentMatchers.<RowMapper<ArchiveVersion>>any(),
                eq(NS), eq(NS), eq("DA00000000000042"), eq("DA00000000000042")))
                .thenReturn(Arrays.asList(version("DA00000000000041", 1), version("DA00000000000042", 2)));
        when(jdbc.query(eq(SnowflakeArchiveStore.EVENTS_SQL), ArgumentMatchers.<RowMapper<ArchiveEvent>>any(),
                eq(NS), eq("DA00000000000041"))).thenReturn(Collections.singletonList(event("FA1", "DA00000000000041")));
        when(jdbc.query(eq(SnowflakeArchiveStore.EVENTS_SQL), ArgumentMatchers.<RowMapper<ArchiveEvent>>any(),
                eq(NS), eq("DA00000000000042"))).thenReturn(Collections.<ArchiveEvent>emptyList());
        RetentionPolicy policy = new RetentionPolicy();
        policy.policyCode = "FIN7";
        when(jdbc.query(eq(SnowflakeArchiveStore.POLICY_SQL), ArgumentMatchers.<RowMapper<RetentionPolicy>>any(),
                eq(NS), eq("FIN7"))).thenReturn(Collections.singletonList(policy));

        Optional<ArchiveDocument> doc = new SnowflakeArchiveStore(jdbc, " s30-after ").findDocument("DA00000000000042");

        assertTrue(doc.isPresent());
        assertEquals("snowflake", doc.get().getStore());
        assertEquals("0f8fad5b-d9cb-469f-a165-70867728950e", doc.get().getDocId());
        assertEquals(2, doc.get().getVersions().size());
        assertEquals("FA1", doc.get().getVersions().get(0).events.get(0).auditKey);
        assertNull(doc.get().getVersions().get(0).events.get(0).archKey);
        assertEquals("FIN7", doc.get().getVersions().get(1).policy.policyCode);
    }

    @Test
    public void unknownKeyIsEmpty() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.query(eq(SnowflakeArchiveStore.VERSIONS_SQL), ArgumentMatchers.<RowMapper<ArchiveVersion>>any(),
                any(), any(), any(), any())).thenReturn(Collections.<ArchiveVersion>emptyList());
        assertFalse(new SnowflakeArchiveStore(jdbc, NS).findDocument("nope").isPresent());
    }

    @Test
    public void driverErrorsBecomeStoreUnavailable() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.query(eq(SnowflakeArchiveStore.VERSIONS_SQL), ArgumentMatchers.<RowMapper<ArchiveVersion>>any(),
                any(), any(), any(), any())).thenThrow(new DataAccessResourceFailureException("390144 JWT token is invalid"));
        try {
            new SnowflakeArchiveStore(jdbc, NS).findDocument("DA1");
            fail("expected unavailable");
        } catch (ArchiveStoreUnavailableException e) {
            assertTrue(e.getMessage().startsWith("snowflake"));
        }
    }

    @Test
    public void sqlReadsTheSplitTargetArchTablesWithoutDriverRounding() {
        assertTrue(SnowflakeArchiveStore.VERSIONS_SQL.contains("FROM ARCH.DOCARCH WHERE NAMESPACE = ?"));
        assertTrue(SnowflakeArchiveStore.VERSIONS_SQL.contains("K.ARCH_KEY = RTRIM(?)"));
        assertTrue(SnowflakeArchiveStore.VERSIONS_SQL.contains("LAST_ACCESS_TS_NANOS_TAIL"));
        assertTrue(SnowflakeArchiveStore.VERSIONS_SQL.contains("FF6"));
        assertTrue(SnowflakeArchiveStore.EVENTS_SQL.contains("FROM ARCH.FILEAUD WHERE NAMESPACE = ? AND ARCH_KEY"));
        assertTrue(SnowflakeArchiveStore.POLICY_SQL.contains("FROM ARCH.RETNPLCY WHERE NAMESPACE = ?"));
    }

    @Test
    public void connectionUsesProgrammaticAccessTokenProperties() {
        ArchiveProperties.Snowflake sf = new ArchiveProperties.Snowflake();
        sf.setAccount("TOJGONB-SF03144");
        sf.setUser("svc_reader");
        sf.setToken("pat-value");
        sf.setRole("LDM_JOB_X1_AFTER");
        sf.setWarehouse("LDM_WH");
        sf.setDatabase("OTTERWORKS_LDM_X1_AFTER");
        assertTrue(sf.isComplete());
        assertEquals("jdbc:snowflake://TOJGONB-SF03144.snowflakecomputing.com/", sf.jdbcUrl());
        Properties props = sf.connectionProperties();
        assertEquals("PROGRAMMATIC_ACCESS_TOKEN", props.getProperty("authenticator"));
        assertEquals("pat-value", props.getProperty("token"));
        assertNull(props.getProperty("password"));
        assertEquals("svc_reader", props.getProperty("user"));
        assertEquals("LDM_JOB_X1_AFTER", props.getProperty("role"));
        assertEquals("LDM_WH", props.getProperty("warehouse"));
        assertEquals("OTTERWORKS_LDM_X1_AFTER", props.getProperty("db"));
        assertFalse(sf.jdbcUrl().contains("pat-value"));
    }
}
