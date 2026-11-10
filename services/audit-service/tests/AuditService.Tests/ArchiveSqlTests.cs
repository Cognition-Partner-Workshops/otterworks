using System.Data.Common;
using System.Reflection;
using Npgsql;
using OtterWorks.AuditService.Archive;

namespace AuditService.Tests;

public class ArchiveSqlTests
{
    private static readonly MethodInfo SetCommandText = typeof(AdoArchiveEventStore)
        .GetMethod("SetCommandText", BindingFlags.NonPublic | BindingFlags.Static)!;

    [Theory]
    [InlineData(Db2ArchiveEventStore.Sql)]
    [InlineData(Db2ArchiveEventStore.VersionsSqlText)]
    [InlineData(PostgresArchiveEventStore.Sql)]
    [InlineData(PostgresArchiveEventStore.VersionsSqlText)]
    [InlineData(AzureSqlArchiveEventStore.Sql)]
    [InlineData(AzureSqlArchiveEventStore.VersionsSqlText)]
    [InlineData("SELECT 1")]
    [InlineData("SELECT 1 FROM SYSIBM.SYSDUMMY1")]
    public void KnownQueriesAreUnchanged(string sql)
    {
        using DbCommand command = new NpgsqlCommand();
        SetCommandText.Invoke(null, new object[] { command, sql });
        Assert.Equal(sql, command.CommandText);
    }

    [Theory]
    [InlineData("")]
    [InlineData("SELECT 1; DROP TABLE FILEAUD")]
    public void UnknownQueriesAreRejected(string sql)
    {
        using DbCommand command = new NpgsqlCommand();
        var error = Assert.Throws<TargetInvocationException>(
            () => SetCommandText.Invoke(null, new object[] { command, sql }));
        Assert.IsType<ArgumentException>(error.InnerException);
        Assert.Equal(string.Empty, command.CommandText);
    }
}
