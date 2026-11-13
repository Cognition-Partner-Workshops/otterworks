using Microsoft.Extensions.Configuration;
using PlatformConfiguration;
using Platform.Shared.Crypto;

namespace TestConfiguration;

public class SigningConfigurationTests
{
    [Fact]
    [Trait("Category","Security")]
    public void MissingKeysFailClosed()
    {
        var error = Assert.Throws<InvalidOperationException>(() => SigningConfiguration.Load(new ConfigurationBuilder().Build()));
        Assert.Contains("Platform:Signing", error.Message);
    }

    [Theory]
    [Trait("Category","Security")]
    [InlineData("AA==")]
    [InlineData("invalid!")]
    public void InvalidKeysFailClosed(string material)
    {
        var settings = SyntheticSigning.Settings;
        settings["Platform:Signing:Keys:0:Material"] = material;
        Assert.Throws<InvalidOperationException>(() => SigningConfiguration.Load(new ConfigurationBuilder().AddInMemoryCollection(settings).Build()));
    }

    [Fact]
    [Trait("Category","Security")]
    public void ConfiguredRingRetainsPreviousKey()
    {
        var settings = SyntheticSigning.Settings;
        settings["Platform:Signing:CurrentKeyId"] = "vsl-synthetic-next";
        settings["Platform:Signing:Keys:1:Id"] = "vsl-synthetic-next";
        settings["Platform:Signing:Keys:1:Material"] = Convert.ToBase64String(Enumerable.Repeat((byte)42, 32).ToArray());
        var provider = SigningConfiguration.Load(new ConfigurationBuilder().AddInMemoryCollection(settings).Build());
        var signature = TokenSigner.Sign("payload", SyntheticSigning.Provider);
        Assert.True(TokenSigner.Verify("payload", signature, provider));
        Assert.False(TokenSigner.Verify("payload", signature, new SigningKeyRing(provider.CurrentKey, new[] { provider.CurrentKey })));
    }
}
