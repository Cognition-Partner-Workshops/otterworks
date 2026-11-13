namespace Platform.Shared.Http;

public sealed class SafeHttpPolicyException : HttpRequestException
{
    public SafeHttpPolicyException(string message) : base(message) { }
}
