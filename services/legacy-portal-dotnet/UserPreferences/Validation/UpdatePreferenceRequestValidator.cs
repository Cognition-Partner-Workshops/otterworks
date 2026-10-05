using FluentValidation;
using OtterWorks.LegacyPortal.UserPreferences.Models;

namespace OtterWorks.LegacyPortal.UserPreferences.Validation;

/// <summary>Java: <c>@NotBlank @Size(max = 20)</c> on <c>theme</c> and <c>locale</c>.</summary>
public sealed class UpdatePreferenceRequestValidator : AbstractValidator<UpdatePreferenceRequest>
{
    public const int MaxLength = 20;

    public UpdatePreferenceRequestValidator()
    {
        RuleFor(r => r.Theme).Must(BeNotBlank).WithMessage("must not be blank").MaximumLength(MaxLength);
        RuleFor(r => r.Locale).Must(BeNotBlank).WithMessage("must not be blank").MaximumLength(MaxLength);
    }

    /// <summary>
    /// Hibernate Validator's <c>@NotBlank</c>: non-null and non-empty after <c>String.trim()</c>, which strips
    /// only characters &lt;= U+0020 (so U+00A0 counts as content, and control characters count as blank).
    /// </summary>
    public static bool BeNotBlank(string? value) => value is not null && value.Any(c => c > ' ');
}
