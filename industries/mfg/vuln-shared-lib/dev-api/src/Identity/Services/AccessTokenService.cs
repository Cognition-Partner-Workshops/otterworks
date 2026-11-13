using System.Text.Json;
using Identity.Models;
using Platform.Shared.Crypto;

namespace Identity.Services;

public sealed class AccessTokenService(TimeProvider clock)
{
    public AccessTokenResponse Create(Account account)
    {
        var issued = clock.GetUtcNow().ToUnixTimeSeconds();
        var payload = Base64Url.Encode(JsonSerializer.SerializeToUtf8Bytes(new
        {
            sub = account.Email,
            dealer = account.DealerId,
            roles = account.Roles.Split(',', StringSplitOptions.RemoveEmptyEntries),
            iat = issued,
            exp = issued + 3600
        }));
        return new($"v1.{payload}.{TokenSigner.Sign(payload)}", "Bearer", 3600, account.DealerId);
    }

    public TokenIdentity? Verify(string token)
    {
        var parts = token.Split('.');
        if (parts.Length != 3 || parts[0] != "v1" || !TokenSigner.Verify(parts[1], parts[2]))
            return null;
        try
        {
            using var json = JsonDocument.Parse(Base64Url.Decode(parts[1]));
            var root = json.RootElement;
            if (root.GetProperty("exp").GetInt64() <= clock.GetUtcNow().ToUnixTimeSeconds())
                return null;
            return new(root.GetProperty("sub").GetString()!, root.GetProperty("dealer").GetString()!,
                root.GetProperty("roles").EnumerateArray().Select(x => x.GetString()!).ToArray());
        }
        catch (Exception e) when (e is JsonException or FormatException or KeyNotFoundException or InvalidOperationException)
        {
            return null;
        }
    }
}

public sealed record TokenIdentity(string Email, string DealerId, string[] Roles);
