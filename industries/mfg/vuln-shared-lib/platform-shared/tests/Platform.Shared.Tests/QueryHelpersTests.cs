using Platform.Shared.Data;

namespace Platform.Shared.Tests;

public class QueryHelpersTests
{
    [Fact]
    public void InClause_NamesOneParameterPerValue()
    {
        var (sql, parameters) = QueryHelpers.InClause("id", new[] { 7, 8, 9 });

        Assert.Equal("@id0, @id1, @id2", sql);
        Assert.Equal(new object?[] { 7, 8, 9 }, parameters.Values);
    }

    [Fact]
    public void InClause_RejectsAnEmptyList()
    {
        Assert.Throws<ArgumentException>(() => QueryHelpers.InClause("id", Array.Empty<int>()));
    }

    [Fact]
    public void LikeContains_EscapesWildcards()
    {
        Assert.Equal("%50\\% off\\_now%", QueryHelpers.LikeContains("50% off_now"));
    }

    [Theory]
    [InlineData("vin", false, "ORDER BY vin ASC")]
    [InlineData("VIN", true, "ORDER BY vin DESC")]
    [InlineData("vin; DROP TABLE dealers", false, "ORDER BY created_at ASC")]
    [InlineData(null, true, "ORDER BY created_at DESC")]
    public void OrderBy_OnlyEmitsAllowlistedColumns(string? column, bool descending, string expected)
    {
        Assert.Equal(expected, QueryHelpers.OrderBy(column, descending, new[] { "vin", "created_at" }, "created_at"));
    }

    [Theory]
    [InlineData(1, 50, 0, 50)]
    [InlineData(3, 20, 40, 20)]
    [InlineData(0, 0, 0, 1)]
    [InlineData(2, 10_000, 200, 200)]
    public void Page_ClampsInputs(int page, int size, int offset, int limit)
    {
        Assert.Equal((offset, limit), QueryHelpers.Page(page, size));
    }
}
