using FluentValidation.TestHelper;
using OtterWorks.LegacyPortal.UserPreferences.Models;
using OtterWorks.LegacyPortal.UserPreferences.Validation;

namespace OtterWorks.LegacyPortal.Tests.Unit.UserPreferences;

public class UpdatePreferenceRequestValidatorTests
{
    private readonly UpdatePreferenceRequestValidator _validator = new();

    [Fact]
    public void Valid_request_passes()
    {
        _validator.TestValidate(Request("dark", "fr-FR")).ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData(1)]
    [InlineData(19)]
    [InlineData(20)]
    public void Lengths_up_to_20_are_accepted(int length)
    {
        var value = new string('t', length);
        _validator.TestValidate(Request(value, value)).ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Length_21_is_rejected_for_theme_and_locale()
    {
        var value = new string('t', 21);
        var result = _validator.TestValidate(Request(value, value));
        result.ShouldHaveValidationErrorFor(r => r.Theme);
        result.ShouldHaveValidationErrorFor(r => r.Locale);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(" ")]
    [InlineData("  \t\r\n")]
    [InlineData("\u0001")]
    public void Blank_values_are_rejected(string? value)
    {
        var result = _validator.TestValidate(Request(value, value));
        result.ShouldHaveValidationErrorFor(r => r.Theme);
        result.ShouldHaveValidationErrorFor(r => r.Locale);
    }

    [Theory]
    [InlineData("\u00a0")]
    [InlineData("\u2003")]
    [InlineData(" x ")]
    public void Values_with_content_beyond_java_trim_are_not_blank(string value)
    {
        _validator.TestValidate(Request(value, value)).ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Length_counts_utf16_code_units_like_java()
    {
        var tenEmoji = string.Concat(Enumerable.Repeat("\U0001F600", 10));
        _validator.TestValidate(Request(tenEmoji, "en-US")).ShouldNotHaveAnyValidationErrors();
        _validator.TestValidate(Request(tenEmoji + "x", "en-US")).ShouldHaveValidationErrorFor(r => r.Theme);
    }

    [Fact]
    public void Email_notifications_is_not_validated()
    {
        _validator.TestValidate(new UpdatePreferenceRequest { Theme = "dark", Locale = "en-US" }).ShouldNotHaveAnyValidationErrors();
    }

    private static UpdatePreferenceRequest Request(string? theme, string? locale) =>
        new() { Theme = theme, Locale = locale, EmailNotifications = true };
}
