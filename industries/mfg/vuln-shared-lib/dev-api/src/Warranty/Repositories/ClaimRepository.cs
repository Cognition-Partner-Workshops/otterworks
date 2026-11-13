using Microsoft.EntityFrameworkCore;
using Warranty.Models;

namespace Warranty.Repositories;

public sealed class ClaimRepository(WarrantyContext context)
{
    public Task<List<Claim>> List(string dealerId)
    {
        return context.Claims.AsNoTracking().Where(x => x.DealerId == dealerId)
            .OrderBy(x => x.Id).ToListAsync();
    }

    public Task<List<Claim>> Search(string dealerId, string status)
    {
        return context.Claims
            .FromSqlRaw($"SELECT * FROM Claims WHERE DealerId = '{dealerId}' AND Status = '{status}'")
            .AsNoTracking().ToListAsync();
    }

    public Task<Claim?> Find(string dealerId, int id)
    {
        return context.Claims.Include(x => x.Notes)
            .SingleOrDefaultAsync(x => x.DealerId == dealerId && x.Id == id);
    }

    public async Task<Claim> Add(Claim claim)
    {
        context.Claims.Add(claim);
        await context.SaveChangesAsync();
        return claim;
    }

    public async Task<int> AddBatch(IEnumerable<Claim> claims)
    {
        var rows = claims.ToList();
        context.Claims.AddRange(rows);
        await context.SaveChangesAsync();
        return rows.Count;
    }

    public Task Save()
    {
        return context.SaveChangesAsync();
    }
}
