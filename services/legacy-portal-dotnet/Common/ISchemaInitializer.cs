namespace OtterWorks.LegacyPortal.Common;

/// <summary>
/// Creates a bounded context's schema/table if missing (Java: <c>spring.jpa.hibernate.ddl-auto=update</c>).
/// Each context registers one; startup runs them all against PostgreSQL.
/// </summary>
public interface ISchemaInitializer
{
    Task InitializeAsync(CancellationToken cancellationToken);
}
