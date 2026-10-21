using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.UserPreferences.Data;

/// <summary>Idempotent equivalent of the DDL Hibernate (<c>ddl-auto=update</c>) generates for <c>UserPreference</c>.</summary>
public sealed class UserPreferencesSchemaInitializer : ISchemaInitializer
{
    public const string Ddl =
        "CREATE SCHEMA IF NOT EXISTS user_preferences; "
        + "CREATE TABLE IF NOT EXISTS user_preferences.user_preference ("
        + "user_id varchar(100) NOT NULL, "
        + "email_notifications boolean NOT NULL, "
        + "locale varchar(20) NOT NULL, "
        + "theme varchar(20) NOT NULL, "
        + "PRIMARY KEY (user_id))";

    private readonly UserPreferencesDbContext _context;

    public UserPreferencesSchemaInitializer(UserPreferencesDbContext context)
    {
        _context = context;
    }

    public async Task InitializeAsync(CancellationToken cancellationToken)
    {
        if (!_context.Database.IsNpgsql())
        {
            return;
        }

        await _context.Database.ExecuteSqlRawAsync(Ddl, cancellationToken);
    }
}
