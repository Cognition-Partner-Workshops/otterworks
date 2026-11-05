namespace OtterWorks.LegacyPortal.Common;

/// <summary>Maps to 404 <c>{"error":"Not Found","message":...}</c> (Java: <c>NoSuchElementException</c>).</summary>
public sealed class PortalNotFoundException : Exception
{
    public PortalNotFoundException(string message)
        : base(message)
    {
    }

    public PortalNotFoundException()
    {
    }

    public PortalNotFoundException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

/// <summary>Maps to 400 <c>{"error":"Bad Request","message":...}</c> (Java: <c>IllegalArgumentException</c>).</summary>
public sealed class PortalValidationException : Exception
{
    public PortalValidationException(string message)
        : base(message)
    {
    }

    public PortalValidationException()
    {
    }

    public PortalValidationException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}
