using OtterWorks.LegacyPortal.UserPreferences.Models;

namespace OtterWorks.LegacyPortal.UserPreferences.Data;

/// <summary>Port of the Java <c>UserPreferenceRepository extends JpaRepository&lt;UserPreference, String&gt;</c>.</summary>
public interface IUserPreferenceRepository
{
    Task<UserPreference?> FindByIdAsync(string userId, CancellationToken cancellationToken);

    /// <summary>Inserts or updates (JPA <c>save</c>/<c>merge</c> semantics) and returns the persisted instance.</summary>
    Task<UserPreference> SaveAsync(UserPreference preference, CancellationToken cancellationToken);
}
