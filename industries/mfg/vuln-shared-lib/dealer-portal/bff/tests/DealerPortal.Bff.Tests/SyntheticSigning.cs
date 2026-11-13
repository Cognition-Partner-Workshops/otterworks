using System.Text;
using Platform.Shared.Crypto;

namespace DealerPortal.Bff.Tests;

public static class SyntheticSigning
{
    public const string VslSyntheticSigningKey = "vsl-synthetic-platform-signing-key-v2-test";
    public static ISigningKeyProvider Provider { get; } = Create();
    private static ISigningKeyProvider Create()
    {
        var key = new SigningKey("vsl-synthetic-test", Encoding.UTF8.GetBytes(VslSyntheticSigningKey));
        return new SigningKeyRing(key, new[] { key });
    }
}
