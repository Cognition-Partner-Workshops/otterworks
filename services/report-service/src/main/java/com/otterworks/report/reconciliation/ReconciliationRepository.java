package com.otterworks.report.reconciliation;

import com.otterworks.report.archive.ArchiveStoreRegistry;
import com.otterworks.report.archive.ArchiveStoreType;
import com.otterworks.report.archive.ArchiveStoreUnavailableException;
import com.otterworks.report.archive.Db2Text;
import com.otterworks.report.reconciliation.ReconciliationReport.ClassTotalRow;
import com.otterworks.report.reconciliation.ReconciliationReport.FailureRow;
import com.otterworks.report.reconciliation.ReconciliationReport.RunSummary;
import com.otterworks.report.reconciliation.ReconciliationReport.SessionLink;
import com.otterworks.report.reconciliation.ReconciliationReport.TableRow;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;

import java.math.BigDecimal;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Reads the migration ledger ({@code mig.*}) straight from the target store, scoped to
 * {@code LDM_NAMESPACE}. No caching, no files (CONTRACTS §10.1).
 *
 * PostgreSQL and Azure SQL hold the whole ledger. On a Snowflake split target the run summary, failures and
 * archive class totals come from the {@code MIG.V_*} views of the Snowflake database; the source side of the class
 * totals and the session links are control-plane rows that only exist in the tenant's PostgreSQL database and are
 * read from there when {@code PG_*} is configured.
 */
public class ReconciliationRepository {

    static final String RUNS_SQL =
            "SELECT run_id, status, started_at, finished_at, closes FROM mig.runs "
            + "WHERE namespace = ? ORDER BY started_at DESC, run_id DESC";

    static final String RUN_SQL =
            "SELECT run_id, status, started_at, finished_at, closes FROM mig.runs "
            + "WHERE namespace = ? AND run_id = ?";

    static final String TABLES_SQL =
            "SELECT table_name, extracted, loaded, validated, purged, failed, rejected, validate_failed, "
            + "purge_intended, purge_dry_run, closes FROM mig.v_reconciliation_tables "
            + "WHERE namespace = ? AND run_id = ? ORDER BY table_order";

    static final String FAILURES_SQL =
            "SELECT table_name, source_key, rule_name, stage, field, sqlstate, native_error, error "
            + "FROM mig.v_reconciliation_failures WHERE namespace = ? AND run_id = ? "
            + "ORDER BY table_name, source_key";

    static final String CLASS_TOTALS_SQL =
            "SELECT table_name, class_code, side, row_count, charge_sum FROM mig.class_totals "
            + "WHERE namespace = ? AND run_id = ? ORDER BY table_name, class_code, side";

    static final String SESSIONS_SQL =
            "SELECT label, url FROM mig.run_sessions WHERE namespace = ? AND run_id = ? ORDER BY ordinal";

    static final String SNOWFLAKE_RUNS_SQL =
            "SELECT RUN_ID AS \"run_id\", MAX(RUN_STATUS) AS \"status\", "
            + "CAST(NULL AS TIMESTAMP_NTZ) AS \"started_at\", "
            + "(SELECT MAX(r.FINISHED_AT) FROM MIG.RUNS r WHERE r.NAMESPACE = s.NAMESPACE AND r.RUN_ID = s.RUN_ID) "
            + "AS \"finished_at\", BOOLAND_AGG(CLOSES) AS \"closes\" "
            + "FROM MIG.V_RUN_SUMMARY s WHERE NAMESPACE = ? GROUP BY NAMESPACE, RUN_ID "
            + "ORDER BY \"finished_at\" DESC NULLS FIRST, \"run_id\" DESC";

    static final String SNOWFLAKE_RUN_SQL =
            "SELECT RUN_ID AS \"run_id\", MAX(RUN_STATUS) AS \"status\", "
            + "CAST(NULL AS TIMESTAMP_NTZ) AS \"started_at\", "
            + "(SELECT MAX(r.FINISHED_AT) FROM MIG.RUNS r WHERE r.NAMESPACE = s.NAMESPACE AND r.RUN_ID = s.RUN_ID) "
            + "AS \"finished_at\", BOOLAND_AGG(CLOSES) AS \"closes\" "
            + "FROM MIG.V_RUN_SUMMARY s WHERE NAMESPACE = ? AND RUN_ID = ? GROUP BY NAMESPACE, RUN_ID";

    static final String SNOWFLAKE_TABLES_SQL =
            "SELECT TABLE_NAME AS \"table_name\", EXTRACTED AS \"extracted\", LOADED AS \"loaded\", "
            + "VALIDATED AS \"validated\", PURGED AS \"purged\", FAILED AS \"failed\", REJECTED AS \"rejected\", "
            + "VALIDATE_FAILED AS \"validate_failed\", PURGE_INTENDED AS \"purge_intended\", "
            + "PURGE_DRY_RUN AS \"purge_dry_run\", CLOSES AS \"closes\" FROM MIG.V_RUN_SUMMARY "
            + "WHERE NAMESPACE = ? AND RUN_ID = ? ORDER BY TABLE_ORDER";

    static final String SNOWFLAKE_FAILURES_SQL =
            "SELECT TABLE_NAME AS \"table_name\", SOURCE_KEY AS \"source_key\", RULE_NAME AS \"rule_name\", "
            + "'VALIDATE' AS \"stage\", CAST(NULL AS VARCHAR) AS \"field\", CAST(NULL AS VARCHAR) AS \"sqlstate\", "
            + "CAST(NULL AS INTEGER) AS \"native_error\", "
            + "IFF(MISSING_ON_TARGET, 'row missing on target', 'target hash differs from source') AS \"error\" "
            + "FROM MIG.V_FAILURES WHERE NAMESPACE = ? AND RUN_ID = ? ORDER BY TABLE_NAME, SOURCE_KEY";

    /** Archive-side (TARGET) totals; {@code MIG.V_CLASS_TOTALS} aggregates {@code ARCH.DOCARCH} per run. */
    static final String SNOWFLAKE_CLASS_TOTALS_SQL =
            "SELECT 'DOCARCH' AS \"table_name\", RETENTION_CLASS AS \"class_code\", 'TARGET' AS \"side\", "
            + "ROW_COUNT AS \"row_count\", CHARGE_SUM AS \"charge_sum\" FROM MIG.V_CLASS_TOTALS "
            + "WHERE NAMESPACE = ? AND MIGRATED_RUN_ID = ? ORDER BY RETENTION_CLASS";

    /**
     * Totals the job recorded in the PostgreSQL control plane, except the DOCARCH archive side, which
     * {@link #SNOWFLAKE_CLASS_TOTALS_SQL} reads from the archive itself.
     */
    static final String CONTROL_CLASS_TOTALS_SQL =
            "SELECT table_name, class_code, side, row_count, charge_sum FROM mig.class_totals "
            + "WHERE namespace = ? AND run_id = ? AND NOT (side = 'TARGET' AND table_name = 'DOCARCH') "
            + "ORDER BY table_name, class_code, side";

    private static final Pattern SEEDED_KEY = Pattern.compile("^MIG(\\d{2})-");
    private static final DateTimeFormatter ISO_UTC = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'");

    private final ArchiveStoreRegistry registry;

    public ReconciliationRepository(ArchiveStoreRegistry registry) {
        this.registry = registry;
    }

    /** True when this namespace has a migration ledger to read (store is postgresql, azuresql or snowflake). */
    public boolean isAvailable() {
        return registry.type().hasMigrationLedger();
    }

    public ArchiveStoreType storeType() {
        return registry.type();
    }

    public String namespace() {
        return registry.namespace();
    }

    /** Source estate driver of the migrated namespace ({@code LDM_SOURCE_PROVIDER}). */
    public String sourceProvider() {
        return registry.sourceProvider();
    }

    /** Target store the ledger and archive are read from ({@code ARCHIVE_STORE}). */
    public String targetProvider() {
        return registry.type().wireName();
    }

    private boolean snowflake() {
        return registry.type() == ArchiveStoreType.SNOWFLAKE;
    }

    public List<RunSummary> listRuns() {
        try {
            List<RunSummary> runs = jdbc().query(snowflake() ? SNOWFLAKE_RUNS_SQL : RUNS_SQL, new RunMapper(),
                    namespace());
            for (RunSummary run : runs) {
                run.source = sourceProvider();
                run.target = targetProvider();
            }
            return runs;
        } catch (DataAccessException e) {
            throw new ArchiveStoreUnavailableException("migration ledger query failed", e);
        }
    }

    public Optional<ReconciliationReport> findRun(String runId) {
        try {
            JdbcTemplate jdbc = jdbc();
            boolean snowflake = snowflake();
            List<RunSummary> runs = jdbc.query(snowflake ? SNOWFLAKE_RUN_SQL : RUN_SQL, new RunMapper(), namespace(),
                    runId);
            if (runs.isEmpty()) {
                return Optional.empty();
            }
            RunSummary run = runs.get(0);
            ReconciliationReport report = new ReconciliationReport();
            report.runId = run.runId;
            report.namespace = namespace();
            report.source = sourceProvider();
            report.target = targetProvider();
            report.status = run.status;
            report.startedAt = run.startedAt;
            report.finishedAt = run.finishedAt;
            report.closes = run.closes;
            report.tables = jdbc.query(snowflake ? SNOWFLAKE_TABLES_SQL : TABLES_SQL, new TableMapper(), namespace(),
                    runId);
            report.failures = jdbc.query(snowflake ? SNOWFLAKE_FAILURES_SQL : FAILURES_SQL, new FailureMapper(),
                    namespace(), runId);
            JdbcTemplate control = snowflake ? registry.controlPlaneJdbc() : jdbc;
            List<ClassSide> sides = new ArrayList<ClassSide>();
            if (control != null) {
                sides.addAll(control.query(snowflake ? CONTROL_CLASS_TOTALS_SQL : CLASS_TOTALS_SQL,
                        new ClassSideMapper(), namespace(), runId));
            }
            if (snowflake) {
                sides.addAll(jdbc.query(SNOWFLAKE_CLASS_TOTALS_SQL, new ClassSideMapper(), namespace(), runId));
            }
            report.classTotals = pivotClassTotals(sides);
            if (control != null) {
                report.sessions = control.query(SESSIONS_SQL, new RowMapper<SessionLink>() {
                    @Override
                    public SessionLink mapRow(ResultSet rs, int rowNum) throws SQLException {
                        return new SessionLink(rs.getString("label"), rs.getString("url"));
                    }
                }, namespace(), runId);
            }
            return Optional.of(report);
        } catch (DataAccessException e) {
            throw new ArchiveStoreUnavailableException("migration ledger query failed", e);
        }
    }

    private JdbcTemplate jdbc() {
        JdbcTemplate jdbc = registry.migrationJdbc();
        if (jdbc == null) {
            registry.store();
            throw new ArchiveStoreUnavailableException("migration ledger requires ARCHIVE_STORE=postgresql, azuresql or snowflake");
        }
        return jdbc;
    }

    /** Ledger DATETIME2 values are stored as UTC wall-clock time; they carry no zone of their own. */
    static String isoUtc(Timestamp ts) {
        if (ts == null) {
            return null;
        }
        return ts.toLocalDateTime().atOffset(ZoneOffset.UTC).format(ISO_UTC);
    }

    /** {@code MIG01-...} keys carry their register id in the key itself. */
    static String issueOf(String trimmedKey) {
        if (trimmedKey == null) {
            return null;
        }
        Matcher m = SEEDED_KEY.matcher(trimmedKey);
        return m.find() ? "MIG-" + m.group(1) : null;
    }

    /** Folds the SOURCE / TARGET rows of {@code mig.class_totals} into one row per table + class. */
    static List<ClassTotalRow> pivotClassTotals(List<ClassSide> sides) {
        Map<String, ClassTotalRow> byKey = new LinkedHashMap<String, ClassTotalRow>();
        for (ClassSide side : sides) {
            String key = side.table + "\u0000" + side.classCode;
            ClassTotalRow row = byKey.get(key);
            if (row == null) {
                row = new ClassTotalRow();
                row.table = side.table;
                row.retentionClass = side.classCode;
                byKey.put(key, row);
            }
            if ("SOURCE".equalsIgnoreCase(side.side)) {
                row.sourceCount = side.rowCount;
                row.sourceSum = side.chargeSum;
            } else {
                row.targetCount = side.rowCount;
                row.targetSum = side.chargeSum;
            }
        }
        List<ClassTotalRow> rows = new ArrayList<ClassTotalRow>(byKey.values());
        for (ClassTotalRow row : rows) {
            boolean sumsMatch = row.sourceSum == null ? row.targetSum == null : row.sourceSum.equals(row.targetSum);
            row.matches = row.sourceCount == row.targetCount && sumsMatch;
        }
        return rows;
    }

    /** One physical row of {@code mig.class_totals}. */
    static final class ClassSide {
        String table;
        String classCode;
        String side;
        long rowCount;
        String chargeSum;
    }

    private static final class RunMapper implements RowMapper<RunSummary> {
        @Override
        public RunSummary mapRow(ResultSet rs, int rowNum) throws SQLException {
            RunSummary run = new RunSummary();
            run.runId = rs.getString("run_id");
            run.status = rs.getString("status");
            run.startedAt = isoUtc(rs.getTimestamp("started_at"));
            run.finishedAt = isoUtc(rs.getTimestamp("finished_at"));
            run.closes = rs.getBoolean("closes") && !rs.wasNull();
            return run;
        }
    }

    private static final class TableMapper implements RowMapper<TableRow> {
        @Override
        public TableRow mapRow(ResultSet rs, int rowNum) throws SQLException {
            TableRow row = new TableRow();
            row.table = rs.getString("table_name");
            row.extracted = rs.getLong("extracted");
            row.loaded = rs.getLong("loaded");
            row.validated = rs.getLong("validated");
            row.purged = rs.getLong("purged");
            row.failed = rs.getLong("failed");
            row.rejected = rs.getLong("rejected");
            row.validateFailed = rs.getLong("validate_failed");
            row.purgeIntended = rs.getLong("purge_intended");
            boolean dryRun = rs.getBoolean("purge_dry_run");
            row.purgeDryRun = rs.wasNull() ? null : Boolean.valueOf(dryRun);
            row.closes = rs.getBoolean("closes");
            return row;
        }
    }

    private static final class FailureMapper implements RowMapper<FailureRow> {
        @Override
        public FailureRow mapRow(ResultSet rs, int rowNum) throws SQLException {
            FailureRow row = new FailureRow();
            row.table = rs.getString("table_name");
            row.sourceKey = Db2Text.rtrim(rs.getString("source_key"));
            row.rule = rs.getString("rule_name");
            row.stage = rs.getString("stage");
            row.field = rs.getString("field");
            row.sqlstate = Db2Text.rtrim(rs.getString("sqlstate"));
            int nativeError = rs.getInt("native_error");
            row.nativeError = rs.wasNull() ? null : Integer.valueOf(nativeError);
            row.error = rs.getString("error");
            row.issue = issueOf(row.sourceKey);
            return row;
        }
    }

    private static final class ClassSideMapper implements RowMapper<ClassSide> {
        @Override
        public ClassSide mapRow(ResultSet rs, int rowNum) throws SQLException {
            ClassSide side = new ClassSide();
            side.table = rs.getString("table_name");
            side.classCode = Db2Text.rtrim(rs.getString("class_code"));
            side.side = rs.getString("side");
            side.rowCount = rs.getLong("row_count");
            BigDecimal sum = rs.getBigDecimal("charge_sum");
            side.chargeSum = sum == null ? null : Db2Text.decimal8(sum);
            return side;
        }
    }
}
