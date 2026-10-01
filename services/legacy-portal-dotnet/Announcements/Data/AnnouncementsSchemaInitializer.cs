using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Announcements.Data;

/// <summary>Idempotent equivalent of the DDL Hibernate (<c>ddl-auto=update</c>) generates for <c>Announcement</c>.</summary>
public sealed class AnnouncementsSchemaInitializer : ISchemaInitializer
{
    public const string Ddl =
        "CREATE SCHEMA IF NOT EXISTS announcements; " +
        "CREATE TABLE IF NOT EXISTS announcements.announcement (" +
        "id bigserial NOT NULL, " +
        "body varchar(4000) NOT NULL, " +
        "created_at timestamp without time zone NOT NULL, " +
        "published boolean NOT NULL, " +
        "title varchar(200) NOT NULL, " +
        "PRIMARY KEY (id));";

    private readonly AnnouncementsDbContext _db;

    public AnnouncementsSchemaInitializer(AnnouncementsDbContext db)
    {
        _db = db;
    }

    public async Task InitializeAsync(CancellationToken cancellationToken)
    {
        if (!_db.Database.IsRelational())
        {
            return;
        }

        await _db.Database.ExecuteSqlRawAsync(Ddl, cancellationToken);
    }
}
