using Platform.Shared.Crypto;

namespace Payments.Services;

public sealed class WebhookSigner(ISigningKeyProvider signingKeys)
{
    public string Sign(string body)
    {
        return TokenSigner.Sign(body, signingKeys);
    }

    public bool Verify(string body, string signature)
    {
        return TokenSigner.Verify(body, signature, signingKeys);
    }
}
