using Microsoft.Extensions.Configuration;
using Platform.Shared.Crypto;

namespace TestConfiguration;

public static class SyntheticSigning
{
    public const string VslSyntheticSigningKey = "vsl-synthetic-platform-signing-key-v2-test";
    public static ISigningKeyProvider Provider { get; } = PlatformConfiguration.SigningConfiguration.Load(
        new ConfigurationBuilder().AddInMemoryCollection(Settings).Build());
    public static Dictionary<string, string?> Settings => new()
    {
        ["Platform:Signing:CurrentKeyId"] = "vsl-synthetic-test",
        ["Platform:Signing:Keys:0:Id"] = "vsl-synthetic-test",
        ["Platform:Signing:Keys:0:Material"] = Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(VslSyntheticSigningKey))
    };
}
