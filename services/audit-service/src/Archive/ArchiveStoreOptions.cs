namespace OtterWorks.AuditService.Archive;

public enum ArchiveStoreType
{
    Off,
    Db2,
    PostgreSql,
    AzureSql,
    Snowflake,
    Invalid,
}

/// <summary>
/// Archive read-path settings, bound from the same environment variables as report-service
/// (ARCHIVE_STORE, DB2_*, PG_*, AZSQL_*, AZURE_CLIENT_ID, SNOWFLAKE_*). Unset ARCHIVE_STORE means feature off.
/// </summary>
public sealed class ArchiveStoreOptions
{
    public string Store { get; set; } = string.Empty;
    public string Namespace { get; set; } = string.Empty;

    public string Db2Host { get; set; } = string.Empty;
    public string Db2Port { get; set; } = "50000";
    public string Db2Database { get; set; } = string.Empty;
    public string Db2User { get; set; } = string.Empty;
    public string Db2Password { get; set; } = string.Empty;

    public string PgHost { get; set; } = string.Empty;
    public string PgPort { get; set; } = "5432";
    public string PgDatabase { get; set; } = string.Empty;
    public string PgUser { get; set; } = string.Empty;
    public string PgPassword { get; set; } = string.Empty;
    public string PgSslMode { get; set; } = "Prefer";

    public string AzsqlServer { get; set; } = string.Empty;
    public string AzsqlDatabase { get; set; } = string.Empty;
    public string AzsqlAuth { get; set; } = "sql";
    public string AzsqlUser { get; set; } = string.Empty;
    public string AzsqlPassword { get; set; } = string.Empty;
    public string AzureClientId { get; set; } = string.Empty;

    public string SnowflakeAccount { get; set; } = string.Empty;
    public string SnowflakeUser { get; set; } = string.Empty;
    public string SnowflakeToken { get; set; } = string.Empty;
    public string SnowflakeRole { get; set; } = string.Empty;
    public string SnowflakeWarehouse { get; set; } = string.Empty;
    public string SnowflakeDatabase { get; set; } = string.Empty;

    public static ArchiveStoreOptions FromEnvironment(Func<string, string?> getEnv) => new()
    {
        Store = getEnv("ARCHIVE_STORE") ?? string.Empty,
        Namespace = getEnv("LDM_NAMESPACE") ?? string.Empty,
        Db2Host = getEnv("DB2_HOST") ?? string.Empty,
        Db2Port = getEnv("DB2_PORT") is { Length: > 0 } port ? port : "50000",
        Db2Database = getEnv("DB2_DATABASE") ?? string.Empty,
        Db2User = getEnv("DB2_USER") ?? string.Empty,
        Db2Password = getEnv("DB2_PASSWORD") ?? string.Empty,
        PgHost = getEnv("PG_HOST") ?? string.Empty,
        PgPort = getEnv("PG_PORT") is { Length: > 0 } pgPort ? pgPort : "5432",
        PgDatabase = getEnv("PG_DATABASE") ?? string.Empty,
        PgUser = getEnv("PG_USER") ?? string.Empty,
        PgPassword = getEnv("PG_PASSWORD") ?? string.Empty,
        PgSslMode = getEnv("PG_SSLMODE") is { Length: > 0 } sslMode ? sslMode : "Prefer",
        AzsqlServer = getEnv("AZSQL_SERVER") ?? string.Empty,
        AzsqlDatabase = getEnv("AZSQL_DATABASE") ?? string.Empty,
        AzsqlAuth = getEnv("AZSQL_AUTH") is { Length: > 0 } auth ? auth : "sql",
        AzsqlUser = getEnv("AZSQL_USER") ?? string.Empty,
        AzsqlPassword = getEnv("AZSQL_PASSWORD") ?? string.Empty,
        AzureClientId = getEnv("AZURE_CLIENT_ID") ?? string.Empty,
        SnowflakeAccount = getEnv("SNOWFLAKE_ACCOUNT") ?? string.Empty,
        SnowflakeUser = getEnv("SNOWFLAKE_USER") ?? string.Empty,
        SnowflakeToken = getEnv("SNOWFLAKE_PAT") ?? string.Empty,
        SnowflakeRole = getEnv("SNOWFLAKE_ROLE") ?? string.Empty,
        SnowflakeWarehouse = getEnv("SNOWFLAKE_WAREHOUSE") ?? string.Empty,
        SnowflakeDatabase = getEnv("SNOWFLAKE_DATABASE") ?? string.Empty,
    };

    public ArchiveStoreType StoreType => Store.Trim().ToLowerInvariant() switch
    {
        "" => ArchiveStoreType.Off,
        "db2" => ArchiveStoreType.Db2,
        "postgresql" or "postgres" => ArchiveStoreType.PostgreSql,
        "azuresql" => ArchiveStoreType.AzureSql,
        "snowflake" => ArchiveStoreType.Snowflake,
        _ => ArchiveStoreType.Invalid,
    };

    public bool IsManagedIdentity =>
        AzsqlAuth.Equals("managed-identity", StringComparison.OrdinalIgnoreCase)
        || AzsqlAuth.Equals("msi", StringComparison.OrdinalIgnoreCase);

    public bool Db2Complete =>
        !string.IsNullOrWhiteSpace(Db2Host) && !string.IsNullOrWhiteSpace(Db2Database)
        && !string.IsNullOrWhiteSpace(Db2User) && !string.IsNullOrWhiteSpace(Db2Password);

    public bool PgComplete =>
        !string.IsNullOrWhiteSpace(PgHost) && !string.IsNullOrWhiteSpace(PgDatabase)
        && !string.IsNullOrWhiteSpace(PgUser) && !string.IsNullOrWhiteSpace(PgPassword);

    public bool AzsqlComplete =>
        !string.IsNullOrWhiteSpace(AzsqlServer) && !string.IsNullOrWhiteSpace(AzsqlDatabase)
        && (IsManagedIdentity || (!string.IsNullOrWhiteSpace(AzsqlUser) && !string.IsNullOrWhiteSpace(AzsqlPassword)));

    public bool SnowflakeComplete =>
        !string.IsNullOrWhiteSpace(SnowflakeAccount) && !string.IsNullOrWhiteSpace(SnowflakeUser)
        && !string.IsNullOrWhiteSpace(SnowflakeToken) && !string.IsNullOrWhiteSpace(SnowflakeDatabase);

    public string Db2ConnectionString =>
        $"Server={Db2Host}:{Db2Port};Database={Db2Database};UID={Db2User};PWD={Db2Password};";

    /// <summary>Npgsql connection string; PG_SSLMODE follows libpq spelling (disable/prefer/require/verify-full).</summary>
    public string PgConnectionString =>
        $"Host={PgHost};Port={PgPort};Database={PgDatabase};Username={PgUser};Password={PgPassword};SSL Mode={PgSslMode};Timeout=30;";

    public string AzsqlConnectionString
    {
        get
        {
            var host = AzsqlServer.Contains('.') ? AzsqlServer : $"{AzsqlServer}.database.windows.net";
            var cs = $"Server=tcp:{host},1433;Database={AzsqlDatabase};Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;";
            if (IsManagedIdentity)
            {
                cs += "Authentication=Active Directory Managed Identity;";
                if (!string.IsNullOrWhiteSpace(AzureClientId))
                {
                    cs += $"User Id={AzureClientId};";
                }
            }
            else
            {
                cs += $"User Id={AzsqlUser};Password={AzsqlPassword};";
            }

            return cs;
        }
    }

    /// <summary>
    /// Snowflake.Data connection string authenticating with the programmatic access token (SNOWFLAKE_PAT).
    /// SNOWFLAKE_ACCOUNT is the org-account identifier (ORG-ACCOUNT); a full host name is used as is.
    /// </summary>
    public string SnowflakeConnectionString
    {
        get
        {
            var account = SnowflakeAccount.Trim();
            var cs = account.Contains('.')
                ? $"host={account};account={account.Split('.')[0]};"
                : $"account={account};";
            cs += $"user={SnowflakeUser.Trim()};authenticator=programmatic_access_token;token={SnowflakeToken.Trim()};"
                + $"db={SnowflakeDatabase.Trim()};";
            if (!string.IsNullOrWhiteSpace(SnowflakeRole))
            {
                cs += $"role={SnowflakeRole.Trim()};";
            }

            if (!string.IsNullOrWhiteSpace(SnowflakeWarehouse))
            {
                cs += $"warehouse={SnowflakeWarehouse.Trim()};";
            }

            return cs;
        }
    }
}
