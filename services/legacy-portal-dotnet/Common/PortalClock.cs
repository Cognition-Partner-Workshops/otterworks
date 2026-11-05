namespace OtterWorks.LegacyPortal.Common;

/// <summary>
/// Timestamps with the precision the Java service persists: <c>Instant.now()</c> stored in a PostgreSQL
/// <c>timestamp</c> column keeps microseconds.
/// </summary>
public static class PortalClock
{
    public static DateTime UtcNow(TimeProvider timeProvider)
    {
        ArgumentNullException.ThrowIfNull(timeProvider);
        return TruncateToMicroseconds(timeProvider.GetUtcNow().UtcDateTime);
    }

    public static DateTime TruncateToMicroseconds(DateTime value)
    {
        return new DateTime(value.Ticks - (value.Ticks % 10), DateTimeKind.Utc);
    }
}
