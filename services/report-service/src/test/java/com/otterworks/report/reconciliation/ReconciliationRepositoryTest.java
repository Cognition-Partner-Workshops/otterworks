package com.otterworks.report.reconciliation;

import com.otterworks.report.archive.ArchiveStoreRegistry;
import com.otterworks.report.archive.ArchiveStoreType;
import com.otterworks.report.reconciliation.ReconciliationReport.ClassTotalRow;
import com.otterworks.report.reconciliation.ReconciliationReport.FailureRow;
import com.otterworks.report.reconciliation.ReconciliationReport.RunSummary;
import com.otterworks.report.reconciliation.ReconciliationReport.TableRow;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import org.mockito.ArgumentMatchers;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;

import java.sql.Timestamp;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Optional;
import java.util.TimeZone;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

public class ReconciliationRepositoryTest {

    private TimeZone original;

    @Before
    public void pinNonUtcZone() {
        original = TimeZone.getDefault();
        TimeZone.setDefault(TimeZone.getTimeZone("America/New_York"));
    }

    @After
    public void restoreZone() {
        TimeZone.setDefault(original);
    }

    @Test
    public void isoUtcKeepsLedgerWallClockOnNonUtcJvm() {
        Timestamp ts = Timestamp.valueOf("2026-09-24 15:00:00");
        assertEquals("2026-09-24T15:00:00Z", ReconciliationRepository.isoUtc(ts));
        assertNull(ReconciliationRepository.isoUtc(null));
    }

    @Test
    public void issueOfReadsSeededRegisterId() {
        assertEquals("MIG-07", ReconciliationRepository.issueOf("MIG07-0000000001"));
        assertNull(ReconciliationRepository.issueOf("DA00000000000042"));
    }

    private static ArchiveStoreRegistry snowflakeRegistry(JdbcTemplate snowflake, JdbcTemplate control) {
        ArchiveStoreRegistry registry = mock(ArchiveStoreRegistry.class);
        when(registry.type()).thenReturn(ArchiveStoreType.SNOWFLAKE);
        when(registry.isConfigured()).thenReturn(true);
        when(registry.namespace()).thenReturn("s30-after");
        when(registry.sourceProvider()).thenReturn("oracle");
        when(registry.migrationJdbc()).thenReturn(snowflake);
        when(registry.controlPlaneJdbc()).thenReturn(control);
        return registry;
    }

    private static ReconciliationRepository.ClassSide side(String cls, String which, long count, String sum) {
        ReconciliationRepository.ClassSide side = new ReconciliationRepository.ClassSide();
        side.table = "DOCARCH";
        side.classCode = cls;
        side.side = which;
        side.rowCount = count;
        side.chargeSum = sum;
        return side;
    }

    @Test
    public void snowflakeRunListReadsRunSummaryViewAndCarriesSourceAndTarget() {
        JdbcTemplate snowflake = mock(JdbcTemplate.class);
        RunSummary run = new RunSummary();
        run.runId = "r20260930060000";
        when(snowflake.query(eq(ReconciliationRepository.SNOWFLAKE_RUNS_SQL),
                ArgumentMatchers.<RowMapper<RunSummary>>any(), eq("s30-after")))
                .thenReturn(Collections.singletonList(run));
        List<RunSummary> runs = new ReconciliationRepository(snowflakeRegistry(snowflake, null)).listRuns();
        assertEquals(1, runs.size());
        assertEquals("oracle", runs.get(0).source);
        assertEquals("snowflake", runs.get(0).target);
        assertTrue(ReconciliationRepository.SNOWFLAKE_RUNS_SQL.contains("FROM MIG.V_RUN_SUMMARY"));
    }

    @Test
    public void emptySnowflakeLedgerHasNoRuns() {
        JdbcTemplate snowflake = mock(JdbcTemplate.class);
        when(snowflake.query(anyString(), ArgumentMatchers.<RowMapper<RunSummary>>any(), eq("s30-after")))
                .thenReturn(Collections.<RunSummary>emptyList());
        when(snowflake.query(anyString(), ArgumentMatchers.<RowMapper<RunSummary>>any(), eq("s30-after"),
                eq("latest"))).thenReturn(Collections.<RunSummary>emptyList());
        ReconciliationRepository repository = new ReconciliationRepository(snowflakeRegistry(snowflake, null));
        assertTrue(repository.listRuns().isEmpty());
        assertFalse(repository.findRun("latest").isPresent());
    }

    @Test
    public void snowflakeReportReadsViewsAndPairsArchiveTotalsWithControlPlaneSourceSide() {
        JdbcTemplate snowflake = mock(JdbcTemplate.class);
        JdbcTemplate control = mock(JdbcTemplate.class);
        RunSummary run = new RunSummary();
        run.runId = "r1";
        run.status = "SUCCEEDED";
        run.closes = true;
        when(snowflake.query(eq(ReconciliationRepository.SNOWFLAKE_RUN_SQL),
                ArgumentMatchers.<RowMapper<RunSummary>>any(), eq("s30-after"), eq("r1")))
                .thenReturn(Collections.singletonList(run));
        TableRow table = new TableRow();
        table.table = "DOCARCH";
        when(snowflake.query(eq(ReconciliationRepository.SNOWFLAKE_TABLES_SQL),
                ArgumentMatchers.<RowMapper<TableRow>>any(), eq("s30-after"), eq("r1")))
                .thenReturn(Collections.singletonList(table));
        FailureRow failure = new FailureRow();
        failure.sourceKey = "MIG07-0000000001";
        when(snowflake.query(eq(ReconciliationRepository.SNOWFLAKE_FAILURES_SQL),
                ArgumentMatchers.<RowMapper<FailureRow>>any(), eq("s30-after"), eq("r1")))
                .thenReturn(Collections.singletonList(failure));
        when(snowflake.query(eq(ReconciliationRepository.SNOWFLAKE_CLASS_TOTALS_SQL),
                ArgumentMatchers.<RowMapper<ReconciliationRepository.ClassSide>>any(), eq("s30-after"), eq("r1")))
                .thenReturn(Collections.singletonList(side("FIN7", "TARGET", 10, "9.50000000")));
        when(control.query(eq(ReconciliationRepository.CONTROL_CLASS_TOTALS_SQL),
                ArgumentMatchers.<RowMapper<ReconciliationRepository.ClassSide>>any(), eq("s30-after"), eq("r1")))
                .thenReturn(Arrays.asList(side("FIN7", "SOURCE", 10, "9.50000000")));

        Optional<ReconciliationReport> report =
                new ReconciliationRepository(snowflakeRegistry(snowflake, control)).findRun("r1");

        assertTrue(report.isPresent());
        assertEquals("oracle", report.get().source);
        assertEquals("snowflake", report.get().target);
        assertEquals("DOCARCH", report.get().tables.get(0).table);
        assertEquals("MIG07-0000000001", report.get().failures.get(0).sourceKey);
        ClassTotalRow totals = report.get().classTotals.get(0);
        assertEquals("FIN7", totals.retentionClass);
        assertEquals(10, totals.sourceCount);
        assertEquals(10, totals.targetCount);
        assertTrue(totals.matches);
        verify(snowflake, never()).query(eq(ReconciliationRepository.RUN_SQL),
                ArgumentMatchers.<RowMapper<RunSummary>>any(), eq("s30-after"), eq("r1"));
        assertTrue(ReconciliationRepository.SNOWFLAKE_FAILURES_SQL.contains("FROM MIG.V_FAILURES"));
        assertTrue(ReconciliationRepository.SNOWFLAKE_CLASS_TOTALS_SQL.contains("FROM MIG.V_CLASS_TOTALS"));
    }
}
