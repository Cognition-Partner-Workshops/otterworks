using Microsoft.EntityFrameworkCore;
using Payments.Models;

namespace Payments.Repositories;

public sealed class PaymentsContext(DbContextOptions<PaymentsContext> options) : DbContext(options)
{
    public DbSet<Settlement> Settlements => Set<Settlement>();
    public DbSet<Refund> Refunds => Set<Refund>();
    public DbSet<WebhookEvent> WebhookEvents => Set<WebhookEvent>();

    protected override void OnModelCreating(ModelBuilder builder)
    {
        builder.Entity<Settlement>().HasIndex(x => new { x.DealerId, x.Reference }).IsUnique();
        builder.Entity<Refund>().HasOne<Settlement>().WithMany().HasForeignKey(x => x.SettlementId);
    }
}
