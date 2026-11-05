using OtterWorks.LegacyPortal.UserPreferences.Data;
using OtterWorks.LegacyPortal.UserPreferences.Models;

namespace OtterWorks.LegacyPortal.UserPreferences.Services;

public sealed class UserPreferenceService : IUserPreferenceService
{
    public const string DefaultTheme = "light";
    public const string DefaultLocale = "en-US";

    private readonly IUserPreferenceRepository _repository;

    public UserPreferenceService(IUserPreferenceRepository repository)
    {
        _repository = repository;
    }

    public async Task<UserPreference> GetOrDefaultAsync(string userId, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(userId);
        return await _repository.FindByIdAsync(userId, cancellationToken) ?? Defaults(userId);
    }

    public async Task<UserPreference> SaveAsync(string userId, string theme, string locale, bool emailNotifications, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(userId);
        var preference = await _repository.FindByIdAsync(userId, cancellationToken) ?? Defaults(userId);
        preference.Theme = theme;
        preference.Locale = locale;
        preference.EmailNotifications = emailNotifications;
        return await _repository.SaveAsync(preference, cancellationToken);
    }

    private static UserPreference Defaults(string userId) => new(userId, DefaultTheme, DefaultLocale, true);
}
