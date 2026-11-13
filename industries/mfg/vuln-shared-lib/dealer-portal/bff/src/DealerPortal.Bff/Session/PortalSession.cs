using System.Text.Json.Serialization;

namespace DealerPortal.Bff.Session;

public sealed record PortalSession(
    [property: JsonPropertyName("sub")] string Email,
    [property: JsonPropertyName("dealer")] string DealerId,
    [property: JsonPropertyName("at")] string AccessToken,
    [property: JsonPropertyName("exp")] long ExpiresAtUnix)
{
    [JsonIgnore]
    public DateTimeOffset ExpiresAt => DateTimeOffset.FromUnixTimeSeconds(ExpiresAtUnix);
}

public sealed record SessionView(string Email, string DealerId, DateTimeOffset ExpiresAt)
{
    public static SessionView From(PortalSession session) => new(session.Email, session.DealerId, session.ExpiresAt);
}
