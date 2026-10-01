using System.Data.Common;
using System.Globalization;
using Snowflake.Data.Client;

namespace OtterWorks.AuditService.Archive;

/// <summary>
/// Reads ARCH.FILEAUD / ARCH.DOCARCH in a split target's Snowflake database
/// (migration/target/snowflake/080_arch_tables.sql). The tables hold every namespace of the tenant database keyed by
/// (NAMESPACE, ARCH_KEY), so each read is scoped to LDM_NAMESPACE. A document is addressed by DOC_ID or by the
/// ARCH_KEY of any of its versions; both resolve to every version of the document and their event trail.
/// TIMESTAMP_NTZ(6) + the six-digit *_NANOS_TAIL rebuild the TIMESTAMP(12) text (CONTRACTS.md §6.0).
/// Parameters are positional (?), bound as "1".."4" in the order <see cref="BindDocId"/> adds them.
/// </summary>
public sealed class SnowflakeArchiveEventStore : AdoArchiveEventStore
{
    private const string DocumentKeys =
        "D.NAMESPACE = ? AND D.DOC_ID IN (SELECT K.DOC_ID FROM ARCH.DOCARCH K WHERE K.NAMESPACE = ? " +
        "AND (K.ARCH_KEY = RTRIM(?) OR RTRIM(K.DOC_ID) = RTRIM(?)))";

    public const string Sql =
        "SELECT F.AUDIT_KEY, F.ARCH_KEY, F.EVENT_TYPE, F.EVENT_TS, F.EVENT_TS_NANOS_TAIL, F.ACTOR_ID, " +
        "F.RETENTION_CLASS, F.DISPOSITION_CODE, F.CLIENT_IP, F.DETAIL_TEXT " +
        "FROM ARCH.DOCARCH D LEFT JOIN ARCH.FILEAUD F ON F.NAMESPACE = D.NAMESPACE AND F.ARCH_KEY = D.ARCH_KEY " +
        "WHERE " + DocumentKeys + " ORDER BY F.EVENT_TS, F.EVENT_TS_NANOS_TAIL, F.AUDIT_KEY";

    public const string VersionsSqlText =
        "SELECT D.ARCH_KEY, D.DOC_ID, D.VERSION_NO, D.RETENTION_CLASS, D.LAST_ACCESS_TS, D.LAST_ACCESS_TS_NANOS_TAIL, " +
        "D.STORAGE_CHARGE, D.OWNER_NAME, D.DISPOSITION_DT, D.LEGAL_HOLD_FLAG " +
        "FROM ARCH.DOCARCH D WHERE " + DocumentKeys + " ORDER BY D.VERSION_NO";

    private readonly string _connectionString;

    public SnowflakeArchiveEventStore(string connectionString, string ns)
    {
        _connectionString = connectionString;
        Namespace = ns.Trim();
    }

    public string Namespace { get; }

    public override string StoreName => "snowflake";

    protected override string EventsSql => Sql;

    protected override string VersionsSql => VersionsSqlText;

    protected override string PingSql => "SELECT 1";

    protected override DbConnection CreateConnection() => new SnowflakeDbConnection { ConnectionString = _connectionString };

    protected override void BindDocId(DbCommand command, string docId)
    {
        foreach (var (position, value) in BindValues(docId))
        {
            AddParameter(command, position, value);
        }
    }

    /// <summary>Positional bind values for <see cref="Sql"/> and <see cref="VersionsSqlText"/>.</summary>
    public IReadOnlyList<(string Position, string Value)> BindValues(string docId) =>
        new[] { ("1", Namespace), ("2", Namespace), ("3", docId), ("4", docId) };

    protected override ArchiveEventRow MapRow(DbDataReader reader) => MapEvent(reader);

    protected override ArchiveVersionRow MapVersion(DbDataReader reader)
    {
        var archKey = Str(reader, "ARCH_KEY");
        var docId = Str(reader, "DOC_ID");
        var ts = reader.GetDateTime(reader.GetOrdinal("LAST_ACCESS_TS"));
        var dispOrdinal = reader.GetOrdinal("DISPOSITION_DT");
        return new ArchiveVersionRow
        {
            ArchKey = Db2Text.RTrim(archKey),
            VersionNo = Int(reader, "VERSION_NO"),
            RetentionClass = Db2Text.RTrim(Str(reader, "RETENTION_CLASS")),
            LastAccessTs = Db2Text.Timestamp12FromMicros(ts, Int(reader, "LAST_ACCESS_TS_NANOS_TAIL")),
            StorageCharge = Db2Text.Decimal8(Convert.ToDecimal(reader.GetValue(reader.GetOrdinal("STORAGE_CHARGE")), CultureInfo.InvariantCulture)),
            OwnerName = Db2Text.RTrim(Str(reader, "OWNER_NAME")),
            DispositionDt = reader.IsDBNull(dispOrdinal)
                ? string.Empty
                : reader.GetDateTime(dispOrdinal).ToString("yyyy-MM-dd", CultureInfo.InvariantCulture),
            LegalHold = Db2Text.RTrim(Str(reader, "LEGAL_HOLD_FLAG")) == "Y",
            Raw = new ArchiveVersionRaw { ArchKey = archKey, DocId = docId },
        };
    }

    public static ArchiveEventRow MapEvent(DbDataReader reader)
    {
        var auditKey = Str(reader, "AUDIT_KEY");
        var archKey = Str(reader, "ARCH_KEY");
        var ts = reader.GetDateTime(reader.GetOrdinal("EVENT_TS"));
        return new ArchiveEventRow
        {
            AuditKey = Db2Text.RTrim(auditKey),
            ArchKey = Db2Text.RTrim(archKey),
            EventType = Db2Text.RTrim(Str(reader, "EVENT_TYPE")),
            EventTs = Db2Text.Timestamp12FromMicros(ts, Int(reader, "EVENT_TS_NANOS_TAIL")),
            ActorId = Db2Text.RTrim(Str(reader, "ACTOR_ID")),
            RetentionClass = Db2Text.RTrim(Str(reader, "RETENTION_CLASS")),
            DispositionCode = Db2Text.RTrim(Str(reader, "DISPOSITION_CODE")),
            ClientIp = Db2Text.RTrim(Str(reader, "CLIENT_IP")),
            DetailText = Db2Text.RTrim(Str(reader, "DETAIL_TEXT")),
            Raw = new ArchiveEventRaw { AuditKey = auditKey, ArchKey = archKey },
        };
    }
}
