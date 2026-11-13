using Platform.Shared.Crypto;

namespace Platform.Shared.Tests;

public class TokenSignerTests
{
    private sealed class FixedKey(string key) : ISigningKeyProvider
    {
        public byte[] CurrentKey { get; } = System.Text.Encoding.UTF8.GetBytes(key);
    }

    private static readonly ISigningKeyProvider Keys = new FixedKey("vsl-synthetic-test-signing-key");

    [Fact]
    public void Sign_DependsOnTheProvidedKey()
    {
        Assert.NotEqual(TokenSigner.Sign("dealer:D-1001", Keys), TokenSigner.Sign("dealer:D-1001", new FixedKey("other")));
    }

    [Fact]
    public void Sign_RejectsMissingKeyProvider()
    {
        Assert.Throws<ArgumentNullException>(() => TokenSigner.Sign("dealer:D-1001", null!));
    }

    [Fact]
    public void Sign_IsDeterministicForTheSamePayload()
    {
        Assert.Equal(TokenSigner.Sign("dealer:D-1001", Keys), TokenSigner.Sign("dealer:D-1001", Keys));
        Assert.NotEqual(TokenSigner.Sign("dealer:D-1001", Keys), TokenSigner.Sign("dealer:D-1002", Keys));
    }

    [Fact]
    public void Sign_ProducesBase64UrlWithoutPadding()
    {
        var signature = TokenSigner.Sign("{\"sub\":\"dealer-ops@dealer.example\"}", Keys);

        Assert.DoesNotContain('=', signature);
        Assert.DoesNotContain('+', signature);
        Assert.DoesNotContain('/', signature);
        Assert.NotEmpty(Base64Url.Decode(signature));
    }

    [Fact]
    public void Verify_AcceptsItsOwnSignatureAndRejectsTampering()
    {
        const string payload = "export:inventory-2026-11.csv";
        var signature = TokenSigner.Sign(payload, Keys);

        Assert.True(TokenSigner.Verify(payload, signature, Keys));
        Assert.False(TokenSigner.Verify(payload + "x", signature, Keys));
        Assert.False(TokenSigner.Verify(payload, signature[..^1] + (signature[^1] == 'A' ? 'B' : 'A'), Keys));
        Assert.False(TokenSigner.Verify(payload, string.Empty, Keys));
    }

    [Fact]
    public void Sign_RejectsNull()
    {
        Assert.Throws<ArgumentNullException>(() => TokenSigner.Sign(null!, Keys));
    }
}
