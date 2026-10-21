using Microsoft.Extensions.Diagnostics.HealthChecks;
using Npgsql;

namespace OtterWorks.LegacyPortal.Common;

/// <summary>Spring's <c>db</c> health indicator: runs a validation query against the shared datasource.</summary>
public sealed class PortalDatabaseHealthCheck : IHealthCheck
{
    private readonly IConfiguration _configuration;

    public PortalDatabaseHealthCheck(IConfiguration configuration)
    {
        _configuration = configuration;
    }

    public async Task<HealthCheckResult> CheckHealthAsync(HealthCheckContext context, CancellationToken cancellationToken = default)
    {
        var settings = DatabaseSettings.FromConfiguration(_configuration);
        if (settings.UsesInMemory)
        {
            return HealthCheckResult.Healthy("EF Core in-memory store");
        }

        var connectionString = new NpgsqlConnectionStringBuilder(settings.BuildConnectionString())
        {
            Timeout = 3,
            CommandTimeout = 3,
        }.ConnectionString;
        try
        {
            await using var connection = new NpgsqlConnection(connectionString);
            await connection.OpenAsync(cancellationToken);
            await using var command = new NpgsqlCommand("SELECT 1", connection);
            await command.ExecuteScalarAsync(cancellationToken);
            return HealthCheckResult.Healthy("PostgreSQL");
        }
        catch (Exception ex) when (ex is NpgsqlException or TimeoutException or System.Net.Sockets.SocketException or InvalidOperationException)
        {
            return HealthCheckResult.Unhealthy("PostgreSQL unreachable", ex);
        }
    }
}
