using Npgsql;

namespace OtterWorks.LegacyPortal.Common;

/// <summary>
/// One datasource shared by all bounded contexts (as in the Java service); each context owns its own schema.
/// Values come from the <c>Database</c> section, overridden by <c>DB_HOST</c>, <c>DB_PORT</c>, <c>DB_NAME</c>,
/// <c>DB_USER</c>, <c>DB_PASSWORD</c> and <c>DB_PROVIDER</c> (<c>Postgres</c> or <c>InMemory</c>).
/// </summary>
public sealed class DatabaseSettings
{
    public string Provider { get; init; } = "Postgres";

    public string Host { get; init; } = "localhost";

    public int Port { get; init; } = 5432;

    public string Name { get; init; } = "legacyportal";

    public string User { get; init; } = "legacyportal";

    public string Password { get; init; } = string.Empty;

    public string InMemoryName { get; init; } = "legacy-portal";

    public bool UsesInMemory => string.Equals(Provider, "InMemory", StringComparison.OrdinalIgnoreCase);

    public static DatabaseSettings FromConfiguration(IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(configuration);
        var section = configuration.GetSection("Database");
        var defaults = new DatabaseSettings();
        return new DatabaseSettings
        {
            Provider = configuration["DB_PROVIDER"] ?? section["Provider"] ?? defaults.Provider,
            Host = configuration["DB_HOST"] ?? section["Host"] ?? defaults.Host,
            Port = int.TryParse(configuration["DB_PORT"] ?? section["Port"], out var port) ? port : defaults.Port,
            Name = configuration["DB_NAME"] ?? section["Name"] ?? defaults.Name,
            User = configuration["DB_USER"] ?? section["User"] ?? defaults.User,
            Password = configuration["DB_PASSWORD"] ?? section["Password"] ?? defaults.Password,
            InMemoryName = section["InMemoryName"] ?? defaults.InMemoryName,
        };
    }

    public string BuildConnectionString()
    {
        return new NpgsqlConnectionStringBuilder
        {
            Host = Host,
            Port = Port,
            Database = Name,
            Username = User,
            Password = Password,
        }.ConnectionString;
    }
}
