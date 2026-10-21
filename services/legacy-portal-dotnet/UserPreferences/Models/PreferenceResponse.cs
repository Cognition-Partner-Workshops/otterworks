namespace OtterWorks.LegacyPortal.UserPreferences.Models;

public sealed record PreferenceResponse(string UserId, string Theme, string Locale, bool EmailNotifications)
{
    public static PreferenceResponse FromEntity(UserPreference preference)
    {
        ArgumentNullException.ThrowIfNull(preference);
        return new PreferenceResponse(preference.UserId, preference.Theme, preference.Locale, preference.EmailNotifications);
    }
}
