using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.UserPreferences.Models;

namespace OtterWorks.LegacyPortal.UserPreferences.Data;

public sealed class UserPreferenceRepository : IUserPreferenceRepository
{
    private readonly UserPreferencesDbContext _context;

    public UserPreferenceRepository(UserPreferencesDbContext context)
    {
        _context = context;
    }

    public async Task<UserPreference?> FindByIdAsync(string userId, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(userId);
        return await _context.Preferences.FindAsync([userId], cancellationToken);
    }

    public async Task<UserPreference> SaveAsync(UserPreference preference, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(preference);
        var managed = preference;
        if (_context.Entry(preference).State == EntityState.Detached)
        {
            var existing = await _context.Preferences.FindAsync([preference.UserId], cancellationToken);
            if (existing is null)
            {
                _context.Preferences.Add(preference);
            }
            else
            {
                _context.Entry(existing).CurrentValues.SetValues(preference);
                managed = existing;
            }
        }

        await _context.SaveChangesAsync(cancellationToken);
        return managed;
    }
}
