using Dealer.Services;

namespace Dealer.Tests;

public sealed class ExportLinkSignerTests
{
    [Fact]
    public void ExportSignatureChecksNameAndExpiry()
    {
        var signer = new ExportLinkSigner(TimeProvider.System, TestConfiguration.SyntheticSigning.Provider);
        var expires = DateTimeOffset.UtcNow.AddMinutes(15).ToUnixTimeSeconds();
        var signature = signer.Sign("stock.csv", expires);
        Assert.True(signer.Verify("stock.csv", expires, signature));
        Assert.False(signer.Verify("other.csv", expires, signature));
        Assert.False(signer.Verify("stock.csv", 1, signer.Sign("stock.csv", 1)));
        Assert.False(signer.Verify("stock.csv", expires, ""));
    }
}
