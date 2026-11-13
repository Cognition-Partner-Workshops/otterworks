using Platform.Shared.Crypto;

namespace Platform.Shared.Tests;

[Collection(SafeHttpCollection.Name)]
public class TokenSignerTests
{
    private static readonly SigningKey Key = new("vsl-synthetic-test", Enumerable.Repeat((byte)42, 32).ToArray());
    private static readonly SigningKeyRing Provider = new(Key, new[] { Key });

    [Fact]
    public void Sign_IsDeterministicForTheSamePayload()
    {
        Assert.Equal(TokenSigner.Sign("dealer:D-1001", Provider), TokenSigner.Sign("dealer:D-1001", Provider));
        Assert.NotEqual(TokenSigner.Sign("dealer:D-1001", Provider), TokenSigner.Sign("dealer:D-1002", Provider));
    }

    [Fact]
    public void Sign_ProducesBase64UrlWithoutPadding()
    {
        var signature = TokenSigner.Sign("{\"sub\":\"dealer-ops@dealer.example\"}", Provider);

        Assert.DoesNotContain('=', signature);
        Assert.DoesNotContain('+', signature);
        Assert.DoesNotContain('/', signature);
        Assert.NotEmpty(Base64Url.Decode(signature));
    }

    [Fact]
    public void Verify_AcceptsItsOwnSignatureAndRejectsTampering()
    {
        const string payload = "export:inventory-2026-11.csv";
        var signature = TokenSigner.Sign(payload, Provider);

        Assert.True(TokenSigner.Verify(payload, signature, Provider));
        Assert.False(TokenSigner.Verify(payload + "x", signature, Provider));
        Assert.False(TokenSigner.Verify(payload, signature[..^1] + (signature[^1] == 'A' ? 'B' : 'A'), Provider));
        Assert.False(TokenSigner.Verify(payload, string.Empty, Provider));
    }

    [Fact]
    public void Sign_RejectsNull()
    {
        Assert.Throws<ArgumentNullException>(() => TokenSigner.Sign(null!, Provider));
    }
}
