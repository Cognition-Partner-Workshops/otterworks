using FluentValidation;
using OtterWorks.LegacyPortal.Announcements.Binding;
using OtterWorks.LegacyPortal.Announcements.Models;

namespace OtterWorks.LegacyPortal.Announcements.Validation;

/// <summary>Java: <c>@NotBlank @Size(max = 200) title</c>, <c>@NotBlank @Size(max = 4000) body</c>.</summary>
public sealed class CreateAnnouncementRequestValidator : AbstractValidator<CreateAnnouncementRequest>
{
    public const int TitleMaxLength = 200;
    public const int BodyMaxLength = 4000;

    public CreateAnnouncementRequestValidator()
    {
        RuleFor(r => r.Title).Must(JavaText.IsNotBlank).WithMessage("must not be blank");
        RuleFor(r => r.Title).MaximumLength(TitleMaxLength);
        RuleFor(r => r.Body).Must(JavaText.IsNotBlank).WithMessage("must not be blank");
        RuleFor(r => r.Body).MaximumLength(BodyMaxLength);
    }
}
