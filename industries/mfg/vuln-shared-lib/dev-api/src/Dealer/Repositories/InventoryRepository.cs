using Dapper;
using Dealer.Models;
using Microsoft.Data.Sqlite;
using Platform.Shared.Data;

namespace Dealer.Repositories;

public sealed class InventoryRepository(IConfiguration configuration)
{
    private SqliteConnection Open()
    {
        var connection = new SqliteConnection(configuration["Dealer:Database"] ?? "Data Source=data/dealer.db");
        connection.Open();
        return connection;
    }

    public void Initialize()
    {
        Directory.CreateDirectory("data");
        using var connection = Open();
        connection.Execute("""
            CREATE TABLE IF NOT EXISTS Inventory (
                Vin TEXT PRIMARY KEY, DealerId TEXT NOT NULL, Model TEXT NOT NULL,
                Year INTEGER NOT NULL, Status TEXT NOT NULL, PriceCents INTEGER NOT NULL,
                ImageUrl TEXT NOT NULL, DaysInStock INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS Bulletins (
                Vin TEXT PRIMARY KEY, PriceCents INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS PriceHistory (
                Id INTEGER PRIMARY KEY, Vin TEXT NOT NULL, PriceCents INTEGER NOT NULL);
            """);
    }

    public async Task<IReadOnlyList<Vehicle>> Inventory(string dealerId, int page, int size)
    {
        var paging = QueryHelpers.Page(page, size);
        using var connection = Open();
        var rows = await connection.QueryAsync<Vehicle>(
            "SELECT * FROM Inventory WHERE DealerId = @dealerId ORDER BY Vin LIMIT @Limit OFFSET @Offset",
            new { dealerId, paging.Limit, paging.Offset });
        return rows.ToList();
    }

    public async Task<IReadOnlyList<Vehicle>> Search(string dealerId, string model)
    {
        using var connection = Open();
        var sql = "SELECT * FROM Inventory WHERE DealerId = @dealerId AND Model LIKE @model ESCAPE '\\'";
        return (await connection.QueryAsync<Vehicle>(sql, new { dealerId, model = QueryHelpers.LikeContains(model) })).ToList();
    }

    public async Task<IReadOnlyList<Vehicle>> Aging(string dealerId, string sort)
    {
        using var connection = Open();
        var parts = sort.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        var valid = parts.Length == 1 || (parts.Length == 2 &&
            (parts[1].Equals("ASC", StringComparison.OrdinalIgnoreCase) || parts[1].Equals("DESC", StringComparison.OrdinalIgnoreCase)));
        var order = QueryHelpers.OrderBy(valid ? parts[0] : null,
            valid && parts.Length == 2 && parts[1].Equals("DESC", StringComparison.OrdinalIgnoreCase),
            new[] { "DaysInStock", "Model", "Year", "PriceCents", "Vin", "Status" }, "Vin");
        return (await connection.QueryAsync<Vehicle>(
            "SELECT * FROM Inventory WHERE DealerId = @dealerId " + order, new { dealerId })).ToList();
    }

    public async Task<Vehicle?> Find(string dealerId, string vin)
    {
        using var connection = Open();
        return await connection.QuerySingleOrDefaultAsync<Vehicle>(
            "SELECT * FROM Inventory WHERE DealerId = @dealerId AND Vin = @vin", new { dealerId, vin });
    }

    public async Task<int> StoreBulletin(IReadOnlyList<BulletinRow> rows)
    {
        using var connection = Open();
        using var transaction = connection.BeginTransaction();
        foreach (var row in rows)
            await connection.ExecuteAsync(
                "INSERT INTO Bulletins(Vin, PriceCents) VALUES (@Vin, @PriceCents) ON CONFLICT(Vin) DO UPDATE SET PriceCents = @PriceCents",
                row, transaction);
        transaction.Commit();
        return rows.Count;
    }

    public async Task<IReadOnlyList<Vehicle>> Browse(string dealerId, string term, string sort, int page, int size)
    {
        var paging = QueryHelpers.Page(page, size);
        var order = QueryHelpers.OrderBy(sort, false, new[] { "Model", "Year", "PriceCents", "Vin" }, "Vin");
        using var connection = Open();
        var rows = await connection.QueryAsync<Vehicle>(
            "SELECT * FROM Inventory WHERE DealerId = @dealerId AND Model LIKE @term ESCAPE '\\' " +
            order + " LIMIT @Limit OFFSET @Offset",
            new { dealerId, term = QueryHelpers.LikeContains(term), paging.Limit, paging.Offset });
        return rows.ToList();
    }

    public async Task<IReadOnlyList<Vehicle>> ByVins(string dealerId, string[] vins)
    {
        if (vins.Length == 0)
        {
            return [];
        }
        var clause = QueryHelpers.InClause("vin", vins);
        var parameters = new DynamicParameters();
        foreach (var pair in clause.Parameters)
        {
            parameters.Add(pair.Key, pair.Value);
        }
        parameters.Add("dealerId", dealerId);
        using var connection = Open();
        return (await connection.QueryAsync<Vehicle>(
            "SELECT * FROM Inventory WHERE DealerId = @dealerId AND Vin IN (" + clause.Sql + ")", parameters)).ToList();
    }

    public async Task<bool> UpdateStatus(string dealerId, string vin, string status)
    {
        using var connection = Open();
        return await connection.ExecuteAsync(
            "UPDATE Inventory SET Status = @status WHERE DealerId = @dealerId AND Vin = @vin",
            new { dealerId, vin, status }) == 1;
    }

    public async Task<bool> UpdatePrice(string dealerId, string vin, long priceCents)
    {
        using var connection = Open();
        using var transaction = connection.BeginTransaction();
        var changed = await connection.ExecuteAsync(
            "UPDATE Inventory SET PriceCents = @priceCents WHERE DealerId = @dealerId AND Vin = @vin",
            new { dealerId, vin, priceCents }, transaction);
        if (changed == 1)
        {
            await connection.ExecuteAsync(
                "INSERT INTO PriceHistory(Vin, PriceCents) VALUES (@vin, @priceCents)",
                new { vin, priceCents }, transaction);
        }
        transaction.Commit();
        return changed == 1;
    }

    public async Task<IReadOnlyList<long>> PriceHistory(string dealerId, string vin)
    {
        using var connection = Open();
        return (await connection.QueryAsync<long>(
            "SELECT h.PriceCents FROM PriceHistory h JOIN Inventory i ON i.Vin = h.Vin " +
            "WHERE i.DealerId = @dealerId AND i.Vin = @vin ORDER BY h.Id", new { dealerId, vin })).ToList();
    }
}
