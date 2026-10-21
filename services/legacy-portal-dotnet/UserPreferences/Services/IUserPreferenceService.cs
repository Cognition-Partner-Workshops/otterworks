using OtterWorks.LegacyPortal.UserPreferences.Models;

namespace OtterWorks.LegacyPortal.UserPreferences.Services;

public interface IUserPreferenceService
{
    /// <summary>Returns stored preferences, or sensible defaults (not persisted) if the user has none yet.</summary>
    Task<UserPreference> GetOrDefaultAsync(string userId, CancellationToken cancellationToken);

    Task<UserPreference> SaveAsync(string userId, string theme, string locale, bool emailNotifications, CancellationToken cancellationToken);
}
