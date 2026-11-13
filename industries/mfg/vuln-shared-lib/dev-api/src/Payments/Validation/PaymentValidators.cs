using FluentValidation;
using Payments.Models;

namespace Payments.Validation;

public sealed class SettlementValidator : AbstractValidator<CreateSettlementRequest>
{
    public SettlementValidator()
    {
        RuleFor(x => x.Reference).NotEmpty().MaximumLength(100);
        RuleFor(x => x.AmountCents).GreaterThan(0);
    }
}

public sealed class RefundValidator : AbstractValidator<RefundRequest>
{
    public RefundValidator()
    {
        RuleFor(x => x.SettlementId).GreaterThan(0);
        RuleFor(x => x.AmountCents).GreaterThan(0);
        RuleFor(x => x.Reason).NotEmpty().MaximumLength(500);
    }
}

public sealed class WebhookTestValidator : AbstractValidator<WebhookTestRequest>
{
    public WebhookTestValidator()
    {
        RuleFor(x => x.Url).Must(value =>
            Uri.TryCreate(value, UriKind.Absolute, out var uri) && uri.Scheme is "https" or "http");
    }
}

public sealed class ProcessorCallbackValidator : AbstractValidator<ProcessorCallbackRequest>
{
    public ProcessorCallbackValidator()
    {
        RuleFor(x => x.SettlementId).GreaterThan(0);
        RuleFor(x => x.Status).Must(value => value is "paid" or "failed");
    }
}
