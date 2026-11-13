using Platform.Shared.Crypto;

namespace Platform.Shared.Tests;

[Collection(SafeHttpCollection.Name)]
public class SigningAndFingerprintTests
{
    private static readonly SigningKey Old = new("vsl-synthetic-old", Enumerable.Range(0, 32).Select(i => (byte)i).ToArray());
    private static readonly SigningKey New = new("vsl-synthetic-new", Enumerable.Repeat((byte)42, 32).ToArray());
    private static SigningKeyRing Ring(SigningKey key) => new(key, new[] { key });

    [Fact]
    public void Sha256_KnownAnswer()
    {
        const string expected = "gAeDfvfwMcdDyxJBuAAahKn2nzw_GlIvBG36YvtCHEY";
        Assert.Equal(expected, TokenSigner.Sign("vsl-synthetic-payload", Ring(Old)));
        Assert.True(TokenSigner.Verify("vsl-synthetic-payload", expected, Ring(Old)));
        Assert.False(TokenSigner.Verify("tampered", expected, Ring(Old)));
        Assert.False(TokenSigner.Verify("vsl-synthetic-payload", expected, Ring(New)));
    }

    [Fact]
    public void Rotation_RetainsThenRemovesOldKey()
    {
        var signature = TokenSigner.Sign("payload", Ring(Old));
        var rotated = new SigningKeyRing(New, new[] { New, Old });
        Assert.Equal(TokenSigner.Sign("payload", Ring(New)), TokenSigner.Sign("payload", rotated));
        Assert.True(TokenSigner.Verify("payload", signature, rotated));
        Assert.False(TokenSigner.Verify("payload", signature, Ring(New)));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("not-a-signature")]
    [InlineData("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")]
    [InlineData("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB")]
    public void MalformedSignature_ReturnsFalse(string? signature) =>
        Assert.False(TokenSigner.Verify("payload", signature!, Ring(Old)));

    [Fact]
    public void KeyValidationAndConfigBinding()
    {
        Assert.Throws<ArgumentException>(() => new SigningKey("vsl-synthetic-short", new byte[31]));
        Assert.Throws<ArgumentNullException>(() => TokenSigner.Sign("payload", null!));
        Assert.Throws<ArgumentNullException>(() => TokenSigner.Verify("payload", "", null!));
        Assert.Throws<FormatException>(() => SigningKey.FromBase64("vsl-synthetic-invalid", "!"));
        Assert.Equal(Old.Material, SigningKey.FromBase64("vsl-synthetic-base64", Convert.ToBase64String(Old.Material)).Material);
        Assert.Equal(Old.Material, SigningKey.FromBase64("vsl-synthetic-base64url", Base64Url.Encode(Old.Material)).Material);
        var copy = Old.Material;
        copy[0] = 99;
        Assert.Equal(0, Old.Material[0]);
    }

    [Fact]
    public void Fingerprint_KnownAnswerAndStability()
    {
        const string expected = "5d7434b86a55836da8cc63110ee7874d8354bd0828f723a53e164fd5fcdc6f5a";
        Assert.Equal(expected, DeviceFingerprint.Compute("vsl-synthetic-agent", "vsl-synthetic-device"));
        Assert.Equal(expected, DeviceFingerprint.Compute("vsl-synthetic-agent", "vsl-synthetic-device"));
        Assert.Equal(DeviceFingerprint.Compute("", ""), DeviceFingerprint.Compute("", ""));
    }

    [Theory]
    [InlineData("ab", "c", "a", "bc")]
    [InlineData("a|b", "c", "a", "b|c")]
    [InlineData("a\0b", "c", "a", "b\0c")]
    [InlineData("{\"a\":1}", "{}", "{\"a\":", "1}{}")]
    public void Fingerprint_FieldsAreUnambiguous(string a, string b, string c, string d) =>
        Assert.NotEqual(DeviceFingerprint.Compute(a, b), DeviceFingerprint.Compute(c, d));

    [Fact]
    public void Fingerprint_RejectsNull()
    {
        Assert.Throws<ArgumentNullException>(() => DeviceFingerprint.Compute(null!, "device"));
        Assert.Throws<ArgumentNullException>(() => DeviceFingerprint.Compute("agent", null!));
    }
}
