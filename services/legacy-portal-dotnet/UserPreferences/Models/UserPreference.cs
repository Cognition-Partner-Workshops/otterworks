namespace OtterWorks.LegacyPortal.UserPreferences.Models;

/// <summary>Bounded context: user-preferences. Owns the <c>user_preferences</c> schema.</summary>
public class UserPreference
{
    public UserPreference(string userId, string theme, string locale, bool emailNotifications)
    {
        UserId = userId;
        Theme = theme;
        Locale = locale;
        EmailNotifications = emailNotifications;
    }

    private UserPreference()
    {
        UserId = string.Empty;
        Theme = string.Empty;
        Locale = string.Empty;
    }

    public string UserId { get; private set; }

    public string Theme { get; set; }

    public string Locale { get; set; }

    public bool EmailNotifications { get; set; }
}
