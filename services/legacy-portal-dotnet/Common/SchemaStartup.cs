namespace OtterWorks.LegacyPortal.Common;

public static class SchemaStartup
{
    /// <summary>Runs every context's <see cref="ISchemaInitializer"/>, retrying while PostgreSQL starts up.</summary>
    public static async Task InitializePortalSchemasAsync(this WebApplication app, int attempts = 15, TimeSpan? delay = null)
    {
        ArgumentNullException.ThrowIfNull(app);
        if (DatabaseSettings.FromConfiguration(app.Configuration).UsesInMemory)
        {
            return;
        }

        var wait = delay ?? TimeSpan.FromSeconds(2);
        for (var attempt = 1; ; attempt++)
        {
            try
            {
                using var scope = app.Services.CreateScope();
                foreach (var initializer in scope.ServiceProvider.GetServices<ISchemaInitializer>())
                {
                    await initializer.InitializeAsync(CancellationToken.None);
                }

                return;
            }
            catch (Exception ex) when (attempt < attempts && ex is Npgsql.NpgsqlException or System.Net.Sockets.SocketException or TimeoutException)
            {
                app.Logger.LogWarning(ex, "Database not ready (attempt {Attempt}/{Attempts}); retrying", attempt, attempts);
                await Task.Delay(wait);
            }
        }
    }
}
