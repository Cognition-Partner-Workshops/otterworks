using OtterWorks.LegacyPortal.Feedback.Models;
using OtterWorks.LegacyPortal.Feedback.Validation;

namespace OtterWorks.LegacyPortal.Tests.Unit.Feedback;

public class SubmitFeedbackRequestValidatorTests
{
    private readonly SubmitFeedbackRequestValidator _validator = new();

    [Fact]
    public void Valid_request_passes()
    {
        _validator.Validate(Valid()).IsValid.Should().BeTrue();
    }

    [Theory]
    [InlineData(0, false)]
    [InlineData(1, true)]
    [InlineData(5, true)]
    [InlineData(6, false)]
    [InlineData(-3, false)]
    public void Rating_boundaries(int rating, bool valid)
    {
        var request = Valid();
        request.Rating = rating;

        var result = _validator.Validate(request);

        result.IsValid.Should().Be(valid);
        if (!valid)
        {
            result.Errors.Should().ContainSingle(e => e.PropertyName == nameof(SubmitFeedbackRequest.Rating));
        }
    }

    [Theory]
    [InlineData(null, false)]
    [InlineData("", false)]
    [InlineData("   ", false)]
    [InlineData("a", true)]
    public void UserId_must_not_be_blank(string? userId, bool valid)
    {
        var request = Valid();
        request.UserId = userId;

        _validator.Validate(request).IsValid.Should().Be(valid);
    }

    [Theory]
    [InlineData(100, true)]
    [InlineData(101, false)]
    public void UserId_max_length_is_100(int length, bool valid)
    {
        var request = Valid();
        request.UserId = new string('u', length);

        _validator.Validate(request).IsValid.Should().Be(valid);
    }

    [Theory]
    [InlineData(null, false)]
    [InlineData("", false)]
    [InlineData("\t\n ", false)]
    [InlineData("x", true)]
    public void Message_must_not_be_blank(string? message, bool valid)
    {
        var request = Valid();
        request.Message = message;

        _validator.Validate(request).IsValid.Should().Be(valid);
    }

    [Theory]
    [InlineData(2000, true)]
    [InlineData(2001, false)]
    public void Message_max_length_is_2000(int length, bool valid)
    {
        var request = Valid();
        request.Message = new string('m', length);

        _validator.Validate(request).IsValid.Should().Be(valid);
    }

    [Fact]
    public void All_fields_invalid_reports_each_field()
    {
        var result = _validator.Validate(new SubmitFeedbackRequest());

        result.Errors.Select(e => e.PropertyName).Distinct().Should().BeEquivalentTo("UserId", "Rating", "Message");
    }

    private static SubmitFeedbackRequest Valid() => new() { UserId = "u1", Rating = 3, Message = "ok" };
}
