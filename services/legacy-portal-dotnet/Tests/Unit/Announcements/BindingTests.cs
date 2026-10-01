using Microsoft.Extensions.Primitives;
using OtterWorks.LegacyPortal.Announcements.Binding;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Tests.Unit.Announcements;

public class BindingTests
{
    [Theory]
    [InlineData("1", 1L)]
    [InlineData("+2", 2L)]
    [InlineData("-3", -3L)]
    [InlineData("007", 7L)]
    [InlineData(" 1 ", 1L)]
    [InlineData("1 2", 12L)]
    [InlineData("0x1F", 31L)]
    [InlineData("#10", 16L)]
    [InlineData("-0x10", -16L)]
    [InlineData("\uFF11", 1L)]
    [InlineData("9223372036854775807", long.MaxValue)]
    [InlineData("-9223372036854775808", long.MinValue)]
    public void Path_long_parses_like_spring(string raw, long expected)
    {
        SpringPathLong.TryParse(raw, out var value).Should().BeTrue();
        value.Should().Be(expected);
    }

    [Theory]
    [InlineData("abc")]
    [InlineData("1.0")]
    [InlineData("9223372036854775808")]
    [InlineData("-9223372036854775809")]
    [InlineData("+")]
    [InlineData("-")]
    [InlineData("1e3")]
    [InlineData("1_000")]
    public void Path_long_rejects_with_for_input_string_message(string raw)
    {
        var act = () => SpringPathLong.TryParse(raw, out _);

        act.Should().Throw<PortalValidationException>().WithMessage($"For input string: \"{raw}\"");
    }

    [Theory]
    [InlineData("")]
    [InlineData(" ")]
    [InlineData("\t")]
    public void Path_long_without_text_is_missing(string raw)
    {
        SpringPathLong.TryParse(raw, out _).Should().BeFalse();
    }

    [Fact]
    public void Path_long_hex_errors_use_decode_messages()
    {
        var act = () => SpringPathLong.TryParse("0x-1", out _);

        act.Should().Throw<PortalValidationException>().WithMessage("Sign character in wrong position");
    }

    [Theory]
    [InlineData(null, true)]
    [InlineData("", true)]
    [InlineData("true", true)]
    [InlineData("TRUE", true)]
    [InlineData(" yes ", true)]
    [InlineData("On", true)]
    [InlineData("1", true)]
    [InlineData("false", false)]
    [InlineData("Off", false)]
    [InlineData("NO", false)]
    [InlineData("0", false)]
    [InlineData(" false\t", false)]
    public void Request_boolean_converts_like_spring(string? raw, bool expected)
    {
        var values = raw is null ? StringValues.Empty : new StringValues(raw);

        SpringRequestBoolean.Parse(values, defaultValue: true).Should().Be(expected);
    }

    [Fact]
    public void Request_boolean_uses_first_value_when_it_converts()
    {
        SpringRequestBoolean.Parse(new StringValues(["false", "true"]), defaultValue: true).Should().BeFalse();
    }

    [Theory]
    [InlineData(new[] { "maybe" }, "maybe")]
    [InlineData(new[] { " " }, " ")]
    [InlineData(new[] { "2" }, "2")]
    [InlineData(new[] { "x", "y" }, "x,y")]
    [InlineData(new[] { "", "no" }, ",no")]
    public void Request_boolean_rejects_with_raw_value(string[] values, string rendered)
    {
        var act = () => SpringRequestBoolean.Parse(new StringValues(values), defaultValue: true);

        act.Should().Throw<PortalValidationException>().WithMessage($"Invalid boolean value [{rendered}]");
    }

    [Theory]
    [InlineData(null, false)]
    [InlineData("", false)]
    [InlineData(" \u0000\u001F", false)]
    [InlineData("a", true)]
    [InlineData("\u00A0", true)]
    public void Not_blank_matches_hibernate_validator(string? value, bool expected)
    {
        JavaText.IsNotBlank(value).Should().Be(expected);
    }
}
