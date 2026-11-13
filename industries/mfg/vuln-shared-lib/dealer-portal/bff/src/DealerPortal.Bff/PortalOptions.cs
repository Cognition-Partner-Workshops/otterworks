namespace DealerPortal.Bff;

public sealed class PortalOptions
{
    public const string Section = "Portal";

    /// <summary>Base URL of the dealer platform API (Identity, Dealer and Warranty).</summary>
    public string DevApiBaseUrl { get; set; } = "http://localhost:5000";

    /// <summary>OEM bulletin feed shown on the Notices screen.</summary>
    public string NoticeFeedUrl { get; set; } = "https://bulletins.oem.example/dealer-notices.json";

    /// <summary>Directory holding the Angular build; relative paths resolve against the content root.</summary>
    public string StaticRoot { get; set; } = "wwwroot";

    public bool SecureCookie { get; set; } = true;
}
