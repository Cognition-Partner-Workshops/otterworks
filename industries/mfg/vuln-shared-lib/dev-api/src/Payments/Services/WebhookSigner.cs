using Platform.Shared.Crypto;

namespace Payments.Services;

public sealed class WebhookSigner
{
    public string Sign(string body)
    {
        return TokenSigner.Sign(body);
    }

    public bool Verify(string body, string signature)
    {
        return TokenSigner.Verify(body, signature);
    }
}
