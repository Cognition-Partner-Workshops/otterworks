using System.Data;
using System.Text;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.Extensions.Logging;
using Moq;
using OtterWorks.AuditService.Archive;
using OtterWorks.AuditService.Controllers;

namespace AuditService.Tests;

public class Db2TextTests
{
    [Fact]
    public void RTrim_RemovesOnlyTrailingSpaces()
    {
        Assert.Equal("  LOPEZ, M.", Db2Text.RTrim("  LOPEZ, M.      "));
        Assert.Equal("A\t", Db2Text.RTrim("A\t  "));
        Assert.Equal(string.Empty, Db2Text.RTrim(null));
    }

    [Fact]
    public void Decimal8_AlwaysHasEightFractionDigits()
    {
        Assert.Equal("1234.50000000", Db2Text.Decimal8(1234.5m));
        Assert.Equal("0.00000000", Db2Text.Decimal8(0m));
        Assert.Equal("-0.12345678", Db2Text.Decimal8(-0.12345678m));
    }

    [Fact]
    public void Timestamp12_FromDb2CharText_IsUnchanged()
    {
        Assert.Equal("2015-07-02-08.00.00.000000000001", Db2Text.Timestamp12("2015-07-02-08.00.00.000000000001"));
    }

    [Fact]
    public void Timestamp12_FromIsoText_PadsFraction()
    {
        Assert.Equal("2016-03-01-10.15.30.123456000000", Db2Text.Timestamp12("2016-03-01 10:15:30.123456"));
        Assert.Equal("2016-03-01-10.15.30.000000000000", Db2Text.Timestamp12("2016-03-01 10:15:30"));
    }

    [Fact]
    public void Timestamp12_FromDateTime2AndNanosTail_ReconstructsExactly()
    {
        var dt = new DateTime(2016, 3, 1, 10, 15, 30).AddTicks(1234567);
        Assert.Equal("2016-03-01-10.15.30.123456789012", Db2Text.Timestamp12(dt, 89012));
        Assert.Equal("2015-07-02-08.00.00.000000000001", Db2Text.Timestamp12(new DateTime(2015, 7, 2, 8, 0, 0), 1));
    }

    [Fact]
    public void DecodeCp037_DecodesEbcdic()
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        var bytes = Encoding.GetEncoding(37).GetBytes("LOPEZ, M.      ");
        Assert.Equal("LOPEZ, M.      ", Db2Text.DecodeCp037(bytes));
    }
}

public class ArchiveStoreOptionsTests
{
    private static ArchiveStoreOptions Opts(params (string, string)[] env)
    {
        var map = env.ToDictionary(e => e.Item1, e => e.Item2);
        return ArchiveStoreOptions.FromEnvironment(k => map.TryGetValue(k, out var v) ? v : null);
    }

    [Fact]
    public void UnsetStore_IsOff()
    {
        Assert.Equal(ArchiveStoreType.Off, Opts().StoreType);
    }

    [Theory]
    [InlineData("db2", ArchiveStoreType.Db2)]
    [InlineData("AzureSQL", ArchiveStoreType.AzureSql)]
    [InlineData("PostgreSQL", ArchiveStoreType.PostgreSql)]
    [InlineData("postgres", ArchiveStoreType.PostgreSql)]
    [InlineData("Snowflake", ArchiveStoreType.Snowflake)]
    [InlineData("oracle", ArchiveStoreType.Invalid)]
    public void StoreType_IsCaseInsensitive(string value, ArchiveStoreType expected)
    {
        Assert.Equal(expected, Opts(("ARCHIVE_STORE", value)).StoreType);
    }

    [Fact]
    public void AzureSql_ManagedIdentity_DoesNotNeedPassword()
    {
        var o = Opts(("ARCHIVE_STORE", "azuresql"), ("AZSQL_SERVER", "sql-x"), ("AZSQL_DATABASE", "db"),
            ("AZSQL_AUTH", "managed-identity"), ("AZURE_CLIENT_ID", "cid"));
        Assert.True(o.AzsqlComplete);
        Assert.Contains("sql-x.database.windows.net", o.AzsqlConnectionString);
        Assert.Contains("Active Directory Managed Identity", o.AzsqlConnectionString);
        Assert.DoesNotContain("Password", o.AzsqlConnectionString);
    }

    [Fact]
    public void Postgres_ConnectionStringAndCompleteness()
    {
        var o = Opts(("ARCHIVE_STORE", "postgresql"), ("PG_HOST", "pg.internal"), ("PG_DATABASE", "otterworks_x1"),
            ("PG_USER", "ldm_reader"), ("PG_PASSWORD", "s3cret"), ("PG_SSLMODE", "require"));
        Assert.True(o.PgComplete);
        Assert.Equal("Host=pg.internal;Port=5432;Database=otterworks_x1;Username=ldm_reader;Password=s3cret;SSL Mode=require;Timeout=30;",
            o.PgConnectionString);
        Assert.False(Opts(("ARCHIVE_STORE", "postgresql"), ("PG_HOST", "pg.internal")).PgComplete);
    }

    [Fact]
    public void Postgres_Timestamp12_RebuildsFromMicrosPlusSixDigitTail()
    {
        var ts = new DateTime(2016, 3, 1, 10, 15, 30).AddTicks(1234560);
        Assert.Equal("2016-03-01-10.15.30.123456789012", Db2Text.Timestamp12FromMicros(ts, 789012));
        Assert.Equal(Db2Text.Timestamp12(new DateTime(2016, 3, 1, 10, 15, 30).AddTicks(1234567), 89012),
            Db2Text.Timestamp12FromMicros(ts, 789012));
        Assert.Equal("2015-07-02-08.00.00.000000000001", Db2Text.Timestamp12FromMicros(new DateTime(2015, 7, 2, 8, 0, 0), 1));
    }

    [Fact]
    public void Db2_IncompleteWithoutPassword()
    {
        var o = Opts(("ARCHIVE_STORE", "db2"), ("DB2_HOST", "h"), ("DB2_DATABASE", "d"), ("DB2_USER", "u"));
        Assert.False(o.Db2Complete);
        Assert.Equal("50000", o.Db2Port);
    }
}

public class ArchiveControllerTests
{
    private static ArchiveStoreRegistry Registry(ArchiveStoreOptions options, IArchiveEventStore? store = null) =>
        new(options, Mock.Of<ILogger<ArchiveStoreRegistry>>(), _ => store ?? Mock.Of<IArchiveEventStore>());

    private static ArchiveStoreOptions Db2Options() => new()
    {
        Store = "db2", Db2Host = "h", Db2Database = "d", Db2User = "u", Db2Password = "p",
    };

    [Fact]
    public async Task FeatureOff_Returns404WithHint()
    {
        var result = await ArchiveController.GetEvents("DOC1", Registry(new ArchiveStoreOptions()), default);
        Assert.Equal(StatusCodes.Status404NotFound, ((IStatusCodeHttpResult)result).StatusCode);
        Assert.Contains("ARCHIVE_STORE=db2", System.Text.Json.JsonSerializer.Serialize(((IValueHttpResult)result).Value));
    }

    [Fact]
    public async Task InvalidStore_Returns503_AndServiceStillConstructs()
    {
        var registry = Registry(new ArchiveStoreOptions { Store = "oracle" });
        Assert.NotNull(registry.ConfigurationError);
        var result = await ArchiveController.GetEvents("DOC1", registry, default);
        Assert.Equal(StatusCodes.Status503ServiceUnavailable, ((IStatusCodeHttpResult)result).StatusCode);
    }

    [Fact]
    public async Task IncompleteDb2Config_Returns503()
    {
        var result = await ArchiveController.GetEvents("DOC1", Registry(new ArchiveStoreOptions { Store = "db2" }), default);
        Assert.Equal(StatusCodes.Status503ServiceUnavailable, ((IStatusCodeHttpResult)result).StatusCode);
    }

    [Fact]
    public async Task UnknownDocument_Returns404()
    {
        var store = new Mock<IArchiveEventStore>();
        store.Setup(s => s.GetEventsAsync("NOPE", It.IsAny<CancellationToken>()))
            .ReturnsAsync((IReadOnlyList<ArchiveEventRow>?)null);
        var result = await ArchiveController.GetEvents("NOPE", Registry(Db2Options(), store.Object), default);
        Assert.Equal(StatusCodes.Status404NotFound, ((IStatusCodeHttpResult)result).StatusCode);
    }

    [Fact]
    public async Task KnownDocument_ReturnsEventsWithStoreName()
    {
        var store = new Mock<IArchiveEventStore>();
        store.SetupGet(s => s.StoreName).Returns("azuresql");
        store.Setup(s => s.GetEventsAsync("DOC42", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ArchiveEventRow>
            {
                new() { AuditKey = "FA000000000000000123", EventType = "VIEW", EventTs = "2015-07-02-08.00.00.000000000001" },
            });
        var result = await ArchiveController.GetEvents("DOC42", Registry(Db2Options(), store.Object), default);
        var ok = Assert.IsType<Ok<ArchiveEventsResponse>>(result);
        Assert.Equal("DOC42", ok.Value!.DocId);
        Assert.Equal("azuresql", ok.Value.Store);
        Assert.Single(ok.Value.Events);
        Assert.Equal("2015-07-02-08.00.00.000000000001", ok.Value.Events[0].EventTs);
    }

    [Fact]
    public async Task GetDocument_ReturnsContractShape_VersionsWithNestedEvents()
    {
        var store = new Mock<IArchiveEventStore>();
        store.SetupGet(s => s.StoreName).Returns("db2");
        store.Setup(s => s.GetDocumentAsync("DOC42", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ArchiveVersionRow>
            {
                new()
                {
                    ArchKey = "DA00000000000042", VersionNo = 3, RetentionClass = "FIN7",
                    LastAccessTs = "2016-03-01-10.15.30.123456789012", StorageCharge = "1234.50000000",
                    OwnerName = "LOPEZ, M.", DispositionDt = "2023-03-01",
                    Events = { new() { AuditKey = "FA000000000000000123", EventType = "VIEW" } },
                },
            });
        var result = await ArchiveController.GetDocument("DOC42", Registry(Db2Options(), store.Object), default);
        var ok = Assert.IsType<Ok<ArchiveDocumentResponse>>(result);
        Assert.Equal("db2", ok.Value!.Store);
        var version = Assert.Single(ok.Value.Versions);
        Assert.Equal(3, version.VersionNo);
        Assert.Equal("1234.50000000", version.StorageCharge);
        Assert.Equal("FA000000000000000123", Assert.Single(version.Events).AuditKey);
    }

    [Fact]
    public async Task GetDocument_UnknownDocument_Is404()
    {
        var store = new Mock<IArchiveEventStore>();
        store.Setup(s => s.GetDocumentAsync("NOPE", It.IsAny<CancellationToken>()))
            .ReturnsAsync((IReadOnlyList<ArchiveVersionRow>?)null);
        var result = await ArchiveController.GetDocument("NOPE", Registry(Db2Options(), store.Object), default);
        Assert.Equal(404, Assert.IsAssignableFrom<IStatusCodeHttpResult>(result).StatusCode);
    }

    [Theory]
    [InlineData("20230301", "2023-03-01")]
    [InlineData("20230301  ", "2023-03-01")]
    [InlineData("\0\0\0\0\0\0\0\0", "\0\0\0\0\0\0\0\0")]
    public void IsoDateFromYyyymmdd_ConvertsDigitsOnly(string input, string expected) =>
        Assert.Equal(expected, Db2Text.IsoDateFromYyyymmdd(input));

    [Fact]
    public async Task StoreFailure_Returns503()
    {
        var store = new Mock<IArchiveEventStore>();
        store.Setup(s => s.GetEventsAsync(It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ThrowsAsync(new ArchiveStoreUnavailableException("db2 archive query failed: SQLSTATE 08001"));
        var result = await ArchiveController.GetEvents("DOC1", Registry(Db2Options(), store.Object), default);
        Assert.Equal(StatusCodes.Status503ServiceUnavailable, ((IStatusCodeHttpResult)result).StatusCode);
    }

    [Fact]
    public async Task ArchiveHealth_OffIsDisabled_UnreachableIs503()
    {
        var off = await ArchiveController.ArchiveHealth(Registry(new ArchiveStoreOptions()), default);
        Assert.Equal(StatusCodes.Status200OK, ((IStatusCodeHttpResult)off).StatusCode);

        var store = new Mock<IArchiveEventStore>();
        store.Setup(s => s.PingAsync(It.IsAny<CancellationToken>()))
            .ThrowsAsync(new ArchiveStoreUnavailableException("down"));
        var down = await ArchiveController.ArchiveHealth(Registry(Db2Options(), store.Object), default);
        Assert.Equal(StatusCodes.Status503ServiceUnavailable, ((IStatusCodeHttpResult)down).StatusCode);
    }

    [Fact]
    public void Sql_NeverTrimsCharColumnsInSelectList()
    {
        Assert.DoesNotContain("RTRIM(F.", Db2ArchiveEventStore.Sql);
        Assert.DoesNotContain("RTRIM(F.", AzureSqlArchiveEventStore.Sql);
        Assert.DoesNotContain("RTRIM(F.", PostgresArchiveEventStore.Sql);
        Assert.Contains("ORDER BY F.EVENT_TS", Db2ArchiveEventStore.Sql);
        Assert.Contains("EVENT_TS_NANOS_TAIL", AzureSqlArchiveEventStore.Sql);
        Assert.Contains("\"EVENT_TS_NANOS_TAIL\"", PostgresArchiveEventStore.Sql);
        Assert.Equal("postgresql", new PostgresArchiveEventStore("Host=x").StoreName);
    }
}

public class SnowflakeArchiveEventStoreTests
{
    private static ArchiveStoreOptions Opts(params (string, string)[] env)
    {
        var map = env.ToDictionary(e => e.Item1, e => e.Item2);
        return ArchiveStoreOptions.FromEnvironment(k => map.TryGetValue(k, out var v) ? v : null);
    }

    private static ArchiveStoreOptions Complete() => Opts(
        ("ARCHIVE_STORE", "snowflake"), ("LDM_NAMESPACE", "s30-after"), ("SNOWFLAKE_ACCOUNT", "TOJGONB-SF03144"),
        ("SNOWFLAKE_USER", "svc_reader"), ("SNOWFLAKE_PAT", "pat-value"), ("SNOWFLAKE_ROLE", "LDM_JOB_X1_AFTER"),
        ("SNOWFLAKE_WAREHOUSE", "LDM_WH"), ("SNOWFLAKE_DATABASE", "OTTERWORKS_LDM_X1_AFTER"));

    [Fact]
    public void Options_BindSnowflakeEnvironmentAndUseProgrammaticAccessToken()
    {
        var o = Complete();
        Assert.Equal(ArchiveStoreType.Snowflake, o.StoreType);
        Assert.True(o.SnowflakeComplete);
        Assert.Equal(
            "account=TOJGONB-SF03144;user=svc_reader;authenticator=programmatic_access_token;token=pat-value;"
            + "db=OTTERWORKS_LDM_X1_AFTER;role=LDM_JOB_X1_AFTER;warehouse=LDM_WH;",
            o.SnowflakeConnectionString);
        Assert.DoesNotContain("password", o.SnowflakeConnectionString, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Options_FullHostNameIsKept()
    {
        var o = Complete();
        o.SnowflakeAccount = "tojgonb-sf03144.privatelink.snowflakecomputing.com";
        Assert.StartsWith("host=tojgonb-sf03144.privatelink.snowflakecomputing.com;account=tojgonb-sf03144;",
            o.SnowflakeConnectionString);
    }

    [Fact]
    public void Registry_WithoutTokenIsUnavailableAndNeverEchoesSecrets()
    {
        var o = Complete();
        o.SnowflakeToken = string.Empty;
        Assert.False(o.SnowflakeComplete);
        var registry = new ArchiveStoreRegistry(o, Mock.Of<ILogger<ArchiveStoreRegistry>>());
        Assert.Contains("SNOWFLAKE_PAT", registry.ConfigurationError);
        Assert.Throws<ArchiveStoreUnavailableException>(() => registry.Store);
    }

    [Fact]
    public void Registry_BuildsTheSnowflakeStoreScopedToTheNamespaceWithoutConnecting()
    {
        var registry = new ArchiveStoreRegistry(Complete(), Mock.Of<ILogger<ArchiveStoreRegistry>>());
        Assert.Null(registry.ConfigurationError);
        var store = Assert.IsType<SnowflakeArchiveEventStore>(registry.Store);
        Assert.Equal("snowflake", store.StoreName);
        Assert.Equal("s30-after", store.Namespace);
    }

    [Fact]
    public void Sql_ReadsFileaudTrailOfEveryVersionByDocIdOrArchKey()
    {
        Assert.Contains("FROM ARCH.DOCARCH D LEFT JOIN ARCH.FILEAUD F ON F.NAMESPACE = D.NAMESPACE AND F.ARCH_KEY = D.ARCH_KEY",
            SnowflakeArchiveEventStore.Sql);
        Assert.Contains("K.ARCH_KEY = RTRIM(?) OR RTRIM(K.DOC_ID) = RTRIM(?)", SnowflakeArchiveEventStore.Sql);
        Assert.Contains("ORDER BY F.EVENT_TS, F.EVENT_TS_NANOS_TAIL, F.AUDIT_KEY", SnowflakeArchiveEventStore.Sql);
        Assert.DoesNotContain("RTRIM(F.", SnowflakeArchiveEventStore.Sql);
        Assert.Contains("FROM ARCH.DOCARCH D WHERE D.NAMESPACE = ?", SnowflakeArchiveEventStore.VersionsSqlText);
        Assert.Equal(4, SnowflakeArchiveEventStore.Sql.Count(c => c == '?'));
        Assert.Equal(4, SnowflakeArchiveEventStore.VersionsSqlText.Count(c => c == '?'));
    }

    [Fact]
    public void BindValues_ScopeToNamespaceThenMatchTheRequestedKey()
    {
        var store = new SnowflakeArchiveEventStore("account=x;", " s30-after ");
        Assert.Equal(
            new[] { ("1", "s30-after"), ("2", "s30-after"), ("3", "DA00000000000042"), ("4", "DA00000000000042") },
            store.BindValues("DA00000000000042"));
    }

    [Fact]
    public void MapEvent_RebuildsTimestamp12FromNumberColumns()
    {
        var table = new DataTable();
        foreach (var column in new[] { "AUDIT_KEY", "ARCH_KEY", "EVENT_TYPE", "ACTOR_ID", "RETENTION_CLASS", "DISPOSITION_CODE", "CLIENT_IP", "DETAIL_TEXT" })
        {
            table.Columns.Add(column, typeof(string));
        }

        table.Columns.Add("EVENT_TS", typeof(DateTime));
        table.Columns.Add("EVENT_TS_NANOS_TAIL", typeof(long));
        var row = table.NewRow();
        row["AUDIT_KEY"] = "FA000000000000000001";
        row["ARCH_KEY"] = "DA00000000000042";
        row["EVENT_TYPE"] = "READ";
        row["ACTOR_ID"] = "USR000000001";
        row["RETENTION_CLASS"] = "FIN7";
        row["DISPOSITION_CODE"] = "RT";
        row["CLIENT_IP"] = "10.0.0.1";
        row["DETAIL_TEXT"] = "viewed";
        row["EVENT_TS"] = new DateTime(2016, 3, 1, 10, 15, 30).AddTicks(1234560);
        row["EVENT_TS_NANOS_TAIL"] = 789012L;
        table.Rows.Add(row);
        using var reader = table.CreateDataReader();
        Assert.True(reader.Read());

        var mapped = SnowflakeArchiveEventStore.MapEvent(reader);

        Assert.Equal("2016-03-01-10.15.30.123456789012", mapped.EventTs);
        Assert.Equal("DA00000000000042", mapped.ArchKey);
        Assert.Equal("FA000000000000000001", mapped.Raw.AuditKey);
        Assert.Equal("READ", mapped.EventType);
    }
}
