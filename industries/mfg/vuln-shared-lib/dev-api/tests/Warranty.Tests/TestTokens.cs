using System.Text.Json;
using Platform.Shared.Crypto;

namespace Warranty.Tests;

public static class TestTokens
{
    public static string Create(long? expires = null, string dealer = "D-1001")
    {
        var issued = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var payload = Base64Url.Encode(JsonSerializer.SerializeToUtf8Bytes(new
        {
            sub = "dealer-ops@dealer.example", dealer, roles = new[] { "dealer", "payments" },
            iat = issued, exp = expires ?? issued + 3600
        }));
        return $"v1.{payload}.{TokenSigner.Sign(payload)}";
    }
}
