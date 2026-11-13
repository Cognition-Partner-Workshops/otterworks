using Warranty.Models;
using Warranty.Validation;

namespace Warranty.Tests;

public sealed class ClaimValidatorTests
{
    [Theory]
    [InlineData("VIN1001", "Door latch", true)]
    [InlineData("", "Door latch", false)]
    [InlineData("VIN1001", "", false)]
    public void CreateValidatesRequiredFields(string vin, string description, bool expected)
    {
        var validator = new CreateClaimValidator();
        Assert.Equal(expected, validator.Validate(new CreateClaimRequest(vin, description)).IsValid);
    }

    [Theory]
    [InlineData("approved", true)]
    [InlineData("reviewing", true)]
    [InlineData("other", false)]
    public void StatusHasKnownValues(string status, bool expected)
    {
        Assert.Equal(expected, new ClaimStatusValidator().Validate(new ClaimStatusRequest(status)).IsValid);
    }

    [Fact]
    public void NotesHaveLengthLimit()
    {
        var validator = new ClaimNoteValidator();
        Assert.True(validator.Validate(new ClaimNoteRequest("Receipt checked")).IsValid);
        Assert.False(validator.Validate(new ClaimNoteRequest(new string('a', 1001))).IsValid);
        Assert.False(validator.Validate(new ClaimNoteRequest("")).IsValid);
    }
}
