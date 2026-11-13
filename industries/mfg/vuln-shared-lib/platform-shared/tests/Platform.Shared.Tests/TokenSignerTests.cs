using Platform.Shared.Crypto;

namespace Platform.Shared.Tests;

#pragma warning disable CS0618

[Collection(SafeHttpCollection.Name)]
public class TokenSignerTests
{
    [Fact]
    public void Sign_IsDeterministicForTheSamePayload()
    {
        Assert.Equal(TokenSigner.Sign("dealer:D-1001"), TokenSigner.Sign("dealer:D-1001"));
        Assert.NotEqual(TokenSigner.Sign("dealer:D-1001"), TokenSigner.Sign("dealer:D-1002"));
    }

    [Fact]
    public void Sign_ProducesBase64UrlWithoutPadding()
    {
        var signature = TokenSigner.Sign("{\"sub\":\"dealer-ops@dealer.example\"}");

        Assert.DoesNotContain('=', signature);
        Assert.DoesNotContain('+', signature);
        Assert.DoesNotContain('/', signature);
        Assert.NotEmpty(Base64Url.Decode(signature));
    }

    [Fact]
    public void Verify_AcceptsItsOwnSignatureAndRejectsTampering()
    {
        const string payload = "export:inventory-2026-11.csv";
        var signature = TokenSigner.Sign(payload);

        Assert.True(TokenSigner.Verify(payload, signature));
        Assert.False(TokenSigner.Verify(payload + "x", signature));
        Assert.False(TokenSigner.Verify(payload, signature[..^1] + (signature[^1] == 'A' ? 'B' : 'A')));
        Assert.False(TokenSigner.Verify(payload, string.Empty));
    }

    [Fact]
    public void Sign_RejectsNull()
    {
        Assert.Throws<ArgumentNullException>(() => TokenSigner.Sign(null!));
    }
}
