using Payments.Models;
using Payments.Repositories;
using Payments.Validation;

namespace Payments.Services;

public sealed class SettlementService(PaymentRepository repository, TimeProvider clock)
{
    public Task<Settlement> Create(string dealerId, CreateSettlementRequest request)
    {
        return repository.Add(new Settlement
        {
            DealerId = dealerId,
            Reference = request.Reference,
            AmountCents = request.AmountCents,
            CreatedAt = clock.GetUtcNow()
        });
    }

    public async Task<int> Import(string dealerId, SettlementBatch batch)
    {
        var validator = new SettlementValidator();
        var rows = new List<Settlement>();
        foreach (var item in batch.Items)
        {
            var amount = checked(item.AmountCents + (item.Adjustment?.AmountCents ?? 0));
            if (!validator.Validate(new CreateSettlementRequest(item.Reference, amount)).IsValid)
            {
                throw new InvalidDataException("A settlement requires a reference and positive amount.");
            }
            rows.Add(new Settlement
            {
                DealerId = dealerId,
                Reference = item.Reference,
                AmountCents = amount,
                CreatedAt = clock.GetUtcNow()
            });
        }
        if (rows.Select(x => x.Reference).Distinct().Count() != rows.Count)
        {
            throw new InvalidDataException("Batch references must be distinct.");
        }
        return await repository.AddBatch(rows);
    }

    public async Task<Refund?> Refund(string dealerId, RefundRequest request)
    {
        var settlement = await repository.Find(dealerId, request.SettlementId);
        if (settlement is null)
        {
            return null;
        }
        var refunded = await repository.Refunded(settlement.Id);
        if (request.AmountCents > settlement.AmountCents - refunded)
        {
            throw new InvalidDataException("Refund exceeds the remaining settlement amount.");
        }
        return await repository.AddRefund(new Refund
        {
            DealerId = dealerId,
            SettlementId = settlement.Id,
            AmountCents = request.AmountCents,
            Reason = request.Reason
        });
    }
}
