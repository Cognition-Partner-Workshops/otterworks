using Microsoft.EntityFrameworkCore;
using Payments.Models;

namespace Payments.Repositories;

public sealed class PaymentRepository(PaymentsContext context)
{
    public Task<List<Settlement>> List(string dealerId)
    {
        return context.Settlements.AsNoTracking().Where(x => x.DealerId == dealerId)
            .OrderBy(x => x.Id).ToListAsync();
    }

    public Task<Settlement?> Find(string dealerId, int id)
    {
        return context.Settlements.SingleOrDefaultAsync(x => x.Id == id && x.DealerId == dealerId);
    }

    public Task<Refund?> FindRefund(int id)
    {
        return context.Refunds.AsNoTracking().SingleOrDefaultAsync(x => x.Id == id);
    }

    public Task<List<Refund>> Refunds(string dealerId)
    {
        return context.Refunds.AsNoTracking().Where(x => x.DealerId == dealerId).ToListAsync();
    }

    public async Task<long> Refunded(int settlementId)
    {
        var amounts = await context.Refunds.Where(x => x.SettlementId == settlementId)
            .Select(x => x.AmountCents).ToListAsync();
        return amounts.Sum();
    }

    public async Task<Settlement> Add(Settlement settlement)
    {
        context.Settlements.Add(settlement);
        await context.SaveChangesAsync();
        return settlement;
    }

    public async Task<int> AddBatch(List<Settlement> settlements)
    {
        context.Settlements.AddRange(settlements);
        await context.SaveChangesAsync();
        return settlements.Count;
    }

    public async Task<Refund> AddRefund(Refund refund)
    {
        context.Refunds.Add(refund);
        await context.SaveChangesAsync();
        return refund;
    }

    public async Task AddEvent(WebhookEvent entry)
    {
        context.WebhookEvents.Add(entry);
        await context.SaveChangesAsync();
    }

    public Task<List<WebhookEvent>> Events(string dealerId)
    {
        return context.WebhookEvents.AsNoTracking().Where(x => x.DealerId == dealerId).ToListAsync();
    }

    public Task Save()
    {
        return context.SaveChangesAsync();
    }
}
