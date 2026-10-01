namespace OtterWorks.LegacyPortal.UserPreferences.Models;

public sealed class UpdatePreferenceRequest
{
    public string? Theme { get; set; }

    public string? Locale { get; set; }

    public bool EmailNotifications { get; set; }
}
