using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Feedback.Data;

/// <summary>Idempotent version of the DDL Hibernate generates for the Java <c>Feedback</c> entity.</summary>
public sealed class FeedbackSchemaInitializer : ISchemaInitializer
{
    public const string Ddl =
        "CREATE SCHEMA IF NOT EXISTS feedback; " +
        "CREATE TABLE IF NOT EXISTS feedback.feedback (" +
        "id bigserial NOT NULL, " +
        "created_at timestamp without time zone NOT NULL, " +
        "message varchar(2000) NOT NULL, " +
        "rating integer NOT NULL, " +
        "user_id varchar(100) NOT NULL, " +
        "PRIMARY KEY (id));";

    private readonly FeedbackDbContext _db;

    public FeedbackSchemaInitializer(FeedbackDbContext db)
    {
        _db = db;
    }

    public async Task InitializeAsync(CancellationToken cancellationToken)
    {
        if (!_db.Database.IsNpgsql())
        {
            return;
        }

        await _db.Database.ExecuteSqlRawAsync(Ddl, cancellationToken);
    }
}
