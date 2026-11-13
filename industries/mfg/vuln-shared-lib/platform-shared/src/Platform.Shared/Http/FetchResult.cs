using System.Net;

namespace Platform.Shared.Http;

public sealed record FetchResult(HttpStatusCode StatusCode, string? ContentType, byte[] Body, Uri FinalUri)
{
    public bool IsSuccess => (int)StatusCode is >= 200 and < 300;
}
