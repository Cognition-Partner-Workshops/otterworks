using Platform.Shared.Crypto;

namespace Dealer.Services;

public sealed class ExportLinkSigner(TimeProvider clock)
{
    public string Sign(string fileName, long expiresUnix) =>
        TokenSigner.Sign($"export:{fileName}:{expiresUnix}");

    public bool Verify(string fileName, long expiresUnix, string signature) =>
        expiresUnix > clock.GetUtcNow().ToUnixTimeSeconds() &&
        TokenSigner.Verify($"export:{fileName}:{expiresUnix}", signature);
}
