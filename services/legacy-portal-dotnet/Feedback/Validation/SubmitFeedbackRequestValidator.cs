using FluentValidation;
using OtterWorks.LegacyPortal.Feedback.Models;

namespace OtterWorks.LegacyPortal.Feedback.Validation;

/// <summary>Java: <c>@NotBlank @Size(max=100) userId</c>, <c>@Min(1) @Max(5) rating</c>, <c>@NotBlank @Size(max=2000) message</c>.</summary>
public sealed class SubmitFeedbackRequestValidator : AbstractValidator<SubmitFeedbackRequest>
{
    public SubmitFeedbackRequestValidator()
    {
        RuleFor(r => r.UserId).NotEmpty().MaximumLength(100);
        RuleFor(r => r.Rating).GreaterThanOrEqualTo(1).LessThanOrEqualTo(5);
        RuleFor(r => r.Message).NotEmpty().MaximumLength(2000);
    }
}
