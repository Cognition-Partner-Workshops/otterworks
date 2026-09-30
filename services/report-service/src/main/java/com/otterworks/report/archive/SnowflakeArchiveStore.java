package com.otterworks.report.archive;

import com.otterworks.report.archive.ArchiveDocument.ArchiveEvent;
import com.otterworks.report.archive.ArchiveDocument.ArchiveVersion;
import com.otterworks.report.archive.ArchiveDocument.RetentionPolicy;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;

/**
 * Reads the migrated {@code ARCH.*} tables of a split target's Snowflake database
 * ({@code migration/target/snowflake/080_arch_tables.sql}).
 *
 * The tables are keyed by {@code (NAMESPACE, ARCH_KEY)}, so every lookup is scoped to {@code LDM_NAMESPACE}. A
 * document is looked up by {@code DOC_ID} or by the {@code ARCH_KEY} of any of its versions (both resolve to all
 * versions of the document), and each version's event trail is read by {@code (NAMESPACE, ARCH_KEY)}.
 * {@code TIMESTAMP_NTZ(6)} is rendered server-side with {@code TO_CHAR ... FF6} so the driver never rounds, and
 * TIMESTAMP(12) text is rebuilt with the six-digit {@code _NANOS_TAIL} exactly like PostgreSQL (CONTRACTS.md §6.0).
 */
public class SnowflakeArchiveStore extends JdbcArchiveStore {

    private static final String TS = "YYYY-MM-DD HH24:MI:SS.FF6";

    static final String VERSIONS_SQL =
            "SELECT ARCH_KEY, DOC_ID, VERSION_NO, RETENTION_CLASS, "
            + "TO_CHAR(LAST_ACCESS_TS, '" + TS + "') AS LAST_ACCESS_TS, LAST_ACCESS_TS_NANOS_TAIL, "
            + "STORAGE_CHARGE, UNIT_RATE, OWNER_NAME, "
            + "TO_CHAR(DISPOSITION_DT, 'YYYY-MM-DD') AS DISPOSITION_DT, "
            + "LEGAL_HOLD_FLAG, CHECKSUM_ALG, CONTENT_SHA256, BYTE_SIZE, SOURCE_SYS "
            + "FROM ARCH.DOCARCH WHERE NAMESPACE = ? AND DOC_ID IN ("
            + "SELECT K.DOC_ID FROM ARCH.DOCARCH K WHERE K.NAMESPACE = ? "
            + "AND (K.ARCH_KEY = RTRIM(?) OR RTRIM(K.DOC_ID) = RTRIM(?))) ORDER BY VERSION_NO";

    static final String EVENTS_SQL =
            "SELECT AUDIT_KEY, ARCH_KEY, EVENT_TYPE, "
            + "TO_CHAR(EVENT_TS, '" + TS + "') AS EVENT_TS, EVENT_TS_NANOS_TAIL, "
            + "ACTOR_ID, RETENTION_CLASS, DISPOSITION_CODE, CLIENT_IP, DETAIL_TEXT "
            + "FROM ARCH.FILEAUD WHERE NAMESPACE = ? AND ARCH_KEY = RTRIM(?) "
            + "ORDER BY EVENT_TS, EVENT_TS_NANOS_TAIL, AUDIT_KEY";

    static final String POLICY_SQL =
            "SELECT POLICY_CODE, POLICY_DESC, RETENTION_YEARS, SUCCESSOR_CODE, ACTIVE_FLAG, "
            + "DISPOSITION_ACTION, TO_CHAR(EFFECTIVE_TS, '" + TS + "') AS EFFECTIVE_TS, "
            + "EFFECTIVE_TS_NANOS_TAIL FROM ARCH.RETNPLCY WHERE NAMESPACE = ? AND RTRIM(POLICY_CODE) = RTRIM(?)";

    static final String PING_SQL = "SELECT 1";

    private final String namespace;

    public SnowflakeArchiveStore(JdbcTemplate jdbc, String namespace) {
        super(jdbc);
        this.namespace = namespace == null ? "" : namespace.trim();
    }

    @Override
    public String storeName() {
        return ArchiveStoreType.SNOWFLAKE.wireName();
    }

    @Override
    protected Object[] args(Object key) {
        return new Object[] {namespace, key};
    }

    @Override
    protected Object[] versionsArgs(String docId) {
        return new Object[] {namespace, namespace, docId, docId};
    }

    @Override
    protected String documentId(String requested, List<ArchiveVersion> versions) {
        return Db2Text.rtrim(versions.get(0).raw.docId);
    }

    @Override
    protected String versionsSql() {
        return VERSIONS_SQL;
    }

    @Override
    protected String eventsSql() {
        return EVENTS_SQL;
    }

    @Override
    protected String policySql() {
        return POLICY_SQL;
    }

    @Override
    protected String pingSql() {
        return PING_SQL;
    }

    @Override
    protected RowMapper<ArchiveVersion> versionMapper() {
        return new RowMapper<ArchiveVersion>() {
            @Override
            public ArchiveVersion mapRow(ResultSet rs, int rowNum) throws SQLException {
                return PostgresArchiveStore.mapVersion(rs);
            }
        };
    }

    @Override
    protected RowMapper<ArchiveEvent> eventMapper() {
        return new RowMapper<ArchiveEvent>() {
            @Override
            public ArchiveEvent mapRow(ResultSet rs, int rowNum) throws SQLException {
                return PostgresArchiveStore.mapEvent(rs);
            }
        };
    }

    @Override
    protected RowMapper<RetentionPolicy> policyMapper() {
        return new RowMapper<RetentionPolicy>() {
            @Override
            public RetentionPolicy mapRow(ResultSet rs, int rowNum) throws SQLException {
                RetentionPolicy p = new RetentionPolicy();
                p.policyCode = Db2Text.rtrim(rs.getString("POLICY_CODE"));
                p.policyDesc = Db2Text.rtrim(rs.getString("POLICY_DESC"));
                p.retentionYears = rs.getInt("RETENTION_YEARS");
                p.successorCode = Db2Text.rtrim(rs.getString("SUCCESSOR_CODE"));
                p.activeFlag = Db2Text.rtrim(rs.getString("ACTIVE_FLAG"));
                p.dispositionAction = Db2Text.rtrim(rs.getString("DISPOSITION_ACTION"));
                p.effectiveTs = Db2Text.timestamp12FromPgTimestamp(
                        rs.getString("EFFECTIVE_TS"), rs.getInt("EFFECTIVE_TS_NANOS_TAIL"));
                return p;
            }
        };
    }
}
