using FluentValidation;
using Warranty.Models;

namespace Warranty.Validation;

public sealed class ClaimImportBatchValidator : AbstractValidator<ClaimImportBatch>
{
    public ClaimImportBatchValidator()
    {
        RuleFor(x => x.Items).NotNull();
        RuleForEach(x => x.Items).NotNull().ChildRules(item =>
        {
            item.RuleFor(x => x.Vin).NotEmpty().MaximumLength(32);
            item.RuleFor(x => x.Description).NotEmpty().MaximumLength(2000);
        });
    }
}

public sealed class CreateClaimValidator : AbstractValidator<CreateClaimRequest>
{
    public CreateClaimValidator()
    {
        RuleFor(x => x.Vin).NotEmpty().MaximumLength(32);
        RuleFor(x => x.Description).NotEmpty().MaximumLength(2000);
    }
}

public sealed class ClaimStatusValidator : AbstractValidator<ClaimStatusRequest>
{
    public ClaimStatusValidator()
    {
        RuleFor(x => x.Status).Must(value => value is "submitted" or "reviewing" or "approved" or "rejected");
    }
}

public sealed class ClaimNoteValidator : AbstractValidator<ClaimNoteRequest>
{
    public ClaimNoteValidator()
    {
        RuleFor(x => x.Text).NotEmpty().MaximumLength(1000);
    }
}
