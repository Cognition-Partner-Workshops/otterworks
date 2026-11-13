using Microsoft.EntityFrameworkCore;
using Warranty.Models;

namespace Warranty.Repositories;

public sealed class WarrantyContext(DbContextOptions<WarrantyContext> options) : DbContext(options)
{
    public DbSet<Claim> Claims => Set<Claim>();
    public DbSet<ClaimNote> Notes => Set<ClaimNote>();

    protected override void OnModelCreating(ModelBuilder builder)
    {
        builder.Entity<Claim>().HasIndex(x => new { x.DealerId, x.Vin });
        builder.Entity<Claim>().HasMany(x => x.Notes).WithOne().HasForeignKey(x => x.ClaimId);
    }
}
