using Payments.Models;
using Payments.Services;
using Payments.Validation;

namespace Payments.Tests;

public sealed class PaymentServiceTests
{
    [Fact]
    [Trait("Category","Security")]
    public void SignatureBindsEventBody()
    {
        var signer = new WebhookSigner();
        var signature = signer.Sign("event-one");
        Assert.True(signer.Verify("event-one", signature));
        Assert.False(signer.Verify("event-two", signature));
        Assert.False(signer.Verify("event-one", ""));
    }

    [Theory]
    [InlineData(1, 500, "Return", true)]
    [InlineData(0, 500, "Return", false)]
    [InlineData(1, 0, "Return", false)]
    [InlineData(1, 500, "", false)]
    public void RefundRequestHasRequiredFields(int id, long amount, string reason, bool expected)
    {
        var result = new RefundValidator().Validate(new RefundRequest(id, amount, reason));
        Assert.Equal(expected, result.IsValid);
    }

    [Theory]
    [InlineData("https://subscriber.dealer.example/events", true)]
    [InlineData("other", false)]
    [InlineData("", false)]
    public void WebhookAddressUsesHttp(string url, bool expected)
    {
        Assert.Equal(expected, new WebhookTestValidator().Validate(new WebhookTestRequest(url)).IsValid);
    }
}
