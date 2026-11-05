using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.UserPreferences.Data;
using OtterWorks.LegacyPortal.UserPreferences.Services;

namespace OtterWorks.LegacyPortal.Tests.Unit.UserPreferences;

/// <summary>Port of the Java <c>UserPreferenceServiceTest</c> (@DataJpaTest): real repository on EF InMemory.</summary>
public sealed class UserPreferenceServiceJavaPortTests : IDisposable
{
    private readonly UserPreferencesDbContext _context;
    private readonly UserPreferenceService _service;

    public UserPreferenceServiceJavaPortTests()
    {
        var options = new DbContextOptionsBuilder<UserPreferencesDbContext>()
            .UseInMemoryDatabase($"prefs-{Guid.NewGuid():N}")
            .Options;
        _context = new UserPreferencesDbContext(options);
        _service = new UserPreferenceService(new UserPreferenceRepository(_context));
    }

    public void Dispose() => _context.Dispose();

    [Fact]
    public async Task UnknownUserGetsDefaults()
    {
        var prefs = await _service.GetOrDefaultAsync("nobody", CancellationToken.None);

        prefs.Theme.Should().Be(UserPreferenceService.DefaultTheme);
        prefs.Locale.Should().Be(UserPreferenceService.DefaultLocale);
        prefs.EmailNotifications.Should().BeTrue();
    }

    [Fact]
    public async Task SavePersistsAndUpdates()
    {
        await _service.SaveAsync("u1", "dark", "fr-FR", false, CancellationToken.None);

        var stored = await _service.GetOrDefaultAsync("u1", CancellationToken.None);
        stored.Theme.Should().Be("dark");
        stored.Locale.Should().Be("fr-FR");
        stored.EmailNotifications.Should().BeFalse();

        await _service.SaveAsync("u1", "light", "en-US", true, CancellationToken.None);
        var updated = await _service.GetOrDefaultAsync("u1", CancellationToken.None);
        updated.Theme.Should().Be("light");
        updated.EmailNotifications.Should().BeTrue();
    }

    [Fact]
    public async Task GetOrDefault_does_not_persist_defaults()
    {
        await _service.GetOrDefaultAsync("nobody", CancellationToken.None);

        (await _context.Preferences.CountAsync()).Should().Be(0);
    }
}
