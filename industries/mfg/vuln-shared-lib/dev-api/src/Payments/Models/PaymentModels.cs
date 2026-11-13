namespace Payments.Models;

public sealed class Settlement
{
    public int Id { get; set; }
    public string DealerId { get; set; } = "";
    public string Reference { get; set; } = "";
    public long AmountCents { get; set; }
    public string Status { get; set; } = "pending";
    public DateTimeOffset CreatedAt { get; set; }
}

public sealed class Refund
{
    public int Id { get; set; }
    public int SettlementId { get; set; }
    public string DealerId { get; set; } = "";
    public long AmountCents { get; set; }
    public string Reason { get; set; } = "";
    public string Status { get; set; } = "requested";
}

public sealed class WebhookEvent
{
    public int Id { get; set; }
    public string DealerId { get; set; } = "";
    public string Body { get; set; } = "";
    public string Signature { get; set; } = "";
    public DateTimeOffset CreatedAt { get; set; }
}

public sealed class SettlementBatch
{
    public List<SettlementImportItem> Items { get; set; } = [];
}

public sealed class SettlementImportItem
{
    public string Reference { get; set; } = "";
    public long AmountCents { get; set; }
    public SettlementAdjustment? Adjustment { get; set; }
}

public abstract class SettlementAdjustment
{
    public long AmountCents { get; set; }
}

public sealed class FeeAdjustment : SettlementAdjustment
{
    public string FeeCode { get; set; } = "";
}

public sealed record CreateSettlementRequest(string Reference, long AmountCents);
public sealed record RefundRequest(int SettlementId, long AmountCents, string Reason);
public sealed record WebhookTestRequest(string Url);
public sealed record ProcessorCallbackRequest(int SettlementId, string Status);
public sealed record RemittanceRow(string Reference, long AmountCents);
