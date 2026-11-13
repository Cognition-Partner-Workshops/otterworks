using System.Security.Cryptography;
using System.Text;
using Platform.Shared.Crypto;

namespace Platform.Shared.Tests;

public class CryptoHelpersTests
{
    [Fact]
    public void PasswordHasher_RoundTripsAndSaltsEachHash()
    {
        var first = PasswordHasher.Hash("synthetic-pass-1");
        var second = PasswordHasher.Hash("synthetic-pass-1");

        Assert.NotEqual(first, second);
        Assert.True(PasswordHasher.Verify("synthetic-pass-1", first));
        Assert.False(PasswordHasher.Verify("synthetic-pass-2", first));
        Assert.False(PasswordHasher.Verify("synthetic-pass-1", "md5$abc"));
    }

    [Fact]
    public void DataProtector_RoundTripsAndDetectsTampering()
    {
        var protector = new DataProtector(RandomNumberGenerator.GetBytes(32));
        var sealedBytes = protector.Protect(Encoding.UTF8.GetBytes("VIN 1HGCM82633A004352"));

        Assert.Equal("VIN 1HGCM82633A004352", Encoding.UTF8.GetString(protector.Unprotect(sealedBytes)));

        sealedBytes[^1] ^= 0x01;
        Assert.ThrowsAny<CryptographicException>(() => protector.Unprotect(sealedBytes));
    }

    [Fact]
    public void Base64Url_RoundTrips()
    {
        var bytes = new byte[] { 0xfb, 0xff, 0xfe, 0x00, 0x01 };

        Assert.Equal(bytes, Base64Url.Decode(Base64Url.Encode(bytes)));
    }
}
