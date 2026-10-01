using OtterWorks.LegacyPortal.Announcements.Models;
using OtterWorks.LegacyPortal.Announcements.Validation;

namespace OtterWorks.LegacyPortal.Tests.Unit.Announcements;

public class CreateAnnouncementRequestValidatorTests
{
    private readonly CreateAnnouncementRequestValidator _validator = new();

    [Theory]
    [InlineData(1, 1)]
    [InlineData(200, 4000)]
    public void Accepts_lengths_within_bounds(int titleLength, int bodyLength)
    {
        var result = _validator.Validate(Request(new string('t', titleLength), new string('b', bodyLength)));

        result.IsValid.Should().BeTrue();
    }

    [Fact]
    public void Rejects_title_over_200_chars()
    {
        var result = _validator.Validate(Request(new string('t', 201), "b"));

        result.Errors.Select(e => e.PropertyName).Should().Equal(nameof(CreateAnnouncementRequest.Title));
    }

    [Fact]
    public void Rejects_body_over_4000_chars()
    {
        var result = _validator.Validate(Request("t", new string('b', 4001)));

        result.Errors.Select(e => e.PropertyName).Should().Equal(nameof(CreateAnnouncementRequest.Body));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(" ")]
    [InlineData("\t\n\r ")]
    [InlineData("\u0001")]
    public void Rejects_blank_title(string? title)
    {
        var result = _validator.Validate(Request(title, "b"));

        result.Errors.Select(e => e.PropertyName).Should().Equal(nameof(CreateAnnouncementRequest.Title));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void Rejects_blank_body(string? body)
    {
        var result = _validator.Validate(Request("t", body));

        result.Errors.Select(e => e.PropertyName).Should().Equal(nameof(CreateAnnouncementRequest.Body));
    }

    [Theory]
    [InlineData("\u00A0")]
    [InlineData("\u2003")]
    public void Unicode_spaces_are_not_blank_like_java_trim(string title)
    {
        _validator.Validate(Request(title, "b")).IsValid.Should().BeTrue();
    }

    [Fact]
    public void Published_defaults_to_false()
    {
        new CreateAnnouncementRequest().Published.Should().BeFalse();
    }

    private static CreateAnnouncementRequest Request(string? title, string? body) => new() { Title = title, Body = body };
}
