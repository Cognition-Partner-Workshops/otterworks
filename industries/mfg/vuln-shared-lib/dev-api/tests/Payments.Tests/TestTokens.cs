using System.Text.Json;
using Platform.Shared.Crypto;

namespace Payments.Tests;

public static class TestTokens
{
    public static string Create(long? expires = null, string dealer = "D-1001", string[]? roles = null)
    {
        var issued = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var payload = Base64Url.Encode(JsonSerializer.SerializeToUtf8Bytes(new
        {
            sub = "dealer-ops@dealer.example", dealer, roles = roles ?? new[] { "dealer", "payments" },
            iat = issued, exp = expires ?? issued + 3600
        }));
        return $"v1.{payload}.{TokenSigner.Sign(payload, TestConfiguration.SyntheticSigning.Provider)}";
    }
}
