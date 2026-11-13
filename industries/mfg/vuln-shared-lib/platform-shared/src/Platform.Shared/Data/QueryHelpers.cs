using System.Text;

namespace Platform.Shared.Data;

/// <summary>
/// Helpers for building parameterized SQL with Dapper or ADO.NET. Values always travel as
/// parameters; only identifiers from a caller-supplied allowlist reach the SQL text.
/// </summary>
public static class QueryHelpers
{
    public const int MaxPageSize = 200;

    /// <summary>Builds <c>@p0, @p1, ...</c> and the matching parameter map for an IN clause.</summary>
    public static (string Sql, IReadOnlyDictionary<string, object?> Parameters) InClause<T>(string prefix, IEnumerable<T> values)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(prefix);
        ArgumentNullException.ThrowIfNull(values);
        var parameters = new Dictionary<string, object?>();
        var sql = new StringBuilder();
        foreach (var value in values)
        {
            var name = $"{prefix}{parameters.Count}";
            if (parameters.Count > 0)
            {
                sql.Append(", ");
            }

            sql.Append('@').Append(name);
            parameters[name] = value;
        }

        if (parameters.Count == 0)
        {
            throw new ArgumentException("An IN clause needs at least one value.", nameof(values));
        }

        return (sql.ToString(), parameters);
    }

    /// <summary>Escapes LIKE wildcards so user text matches literally; use with <c>ESCAPE '\'</c>.</summary>
    public static string LikeContains(string term)
    {
        ArgumentNullException.ThrowIfNull(term);
        var escaped = term.Replace("\\", "\\\\").Replace("%", "\\%").Replace("_", "\\_");
        return $"%{escaped}%";
    }

    /// <summary>Returns an ORDER BY fragment when <paramref name="column"/> is in <paramref name="allowedColumns"/>.</summary>
    public static string OrderBy(string? column, bool descending, IReadOnlyCollection<string> allowedColumns, string fallback)
    {
        ArgumentNullException.ThrowIfNull(allowedColumns);
        ArgumentException.ThrowIfNullOrWhiteSpace(fallback);
        var chosen = column is not null && allowedColumns.Contains(column, StringComparer.OrdinalIgnoreCase)
            ? allowedColumns.First(c => string.Equals(c, column, StringComparison.OrdinalIgnoreCase))
            : fallback;
        return $"ORDER BY {chosen} {(descending ? "DESC" : "ASC")}";
    }

    /// <summary>Clamps page and size and returns the row offset.</summary>
    public static (int Offset, int Limit) Page(int page, int pageSize)
    {
        var limit = Math.Clamp(pageSize, 1, MaxPageSize);
        var offset = (Math.Max(page, 1) - 1) * limit;
        return (offset, limit);
    }
}
