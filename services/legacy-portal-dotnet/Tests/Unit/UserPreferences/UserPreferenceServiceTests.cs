using Moq;
using OtterWorks.LegacyPortal.UserPreferences.Data;
using OtterWorks.LegacyPortal.UserPreferences.Models;
using OtterWorks.LegacyPortal.UserPreferences.Services;

namespace OtterWorks.LegacyPortal.Tests.Unit.UserPreferences;

public class UserPreferenceServiceTests
{
    private readonly Mock<IUserPreferenceRepository> _repository = new(MockBehavior.Strict);
    private readonly UserPreferenceService _service;

    public UserPreferenceServiceTests()
    {
        _service = new UserPreferenceService(_repository.Object);
    }

    [Fact]
    public async Task GetOrDefault_returns_stored_preference()
    {
        var stored = new UserPreference("u1", "dark", "fr-FR", false);
        _repository.Setup(r => r.FindByIdAsync("u1", It.IsAny<CancellationToken>())).ReturnsAsync(stored);

        var result = await _service.GetOrDefaultAsync("u1", CancellationToken.None);

        result.Should().BeSameAs(stored);
    }

    [Fact]
    public async Task GetOrDefault_returns_unsaved_defaults_when_missing()
    {
        _repository.Setup(r => r.FindByIdAsync("nobody", It.IsAny<CancellationToken>())).ReturnsAsync((UserPreference?)null);

        var result = await _service.GetOrDefaultAsync("nobody", CancellationToken.None);

        result.UserId.Should().Be("nobody");
        result.Theme.Should().Be(UserPreferenceService.DefaultTheme).And.Be("light");
        result.Locale.Should().Be(UserPreferenceService.DefaultLocale).And.Be("en-US");
        result.EmailNotifications.Should().BeTrue();
        _repository.Verify(r => r.SaveAsync(It.IsAny<UserPreference>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task Save_creates_new_preference_when_missing()
    {
        _repository.Setup(r => r.FindByIdAsync("u1", It.IsAny<CancellationToken>())).ReturnsAsync((UserPreference?)null);
        UserPreference? captured = null;
        _repository.Setup(r => r.SaveAsync(It.IsAny<UserPreference>(), It.IsAny<CancellationToken>()))
            .Callback<UserPreference, CancellationToken>((p, _) => captured = p)
            .ReturnsAsync((UserPreference p, CancellationToken _) => p);

        var result = await _service.SaveAsync("u1", "dark", "fr-FR", false, CancellationToken.None);

        captured.Should().NotBeNull();
        result.Should().BeSameAs(captured);
        result.UserId.Should().Be("u1");
        result.Theme.Should().Be("dark");
        result.Locale.Should().Be("fr-FR");
        result.EmailNotifications.Should().BeFalse();
    }

    [Fact]
    public async Task Save_updates_existing_preference_in_place()
    {
        var existing = new UserPreference("u1", "dark", "fr-FR", false);
        _repository.Setup(r => r.FindByIdAsync("u1", It.IsAny<CancellationToken>())).ReturnsAsync(existing);
        _repository.Setup(r => r.SaveAsync(existing, It.IsAny<CancellationToken>())).ReturnsAsync(existing);

        var result = await _service.SaveAsync("u1", "light", "en-US", true, CancellationToken.None);

        result.Should().BeSameAs(existing);
        existing.Theme.Should().Be("light");
        existing.Locale.Should().Be("en-US");
        existing.EmailNotifications.Should().BeTrue();
        _repository.Verify(r => r.SaveAsync(existing, It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task Save_returns_the_instance_the_repository_returns()
    {
        var persisted = new UserPreference("u1", "dark", "de-DE", true);
        _repository.Setup(r => r.FindByIdAsync("u1", It.IsAny<CancellationToken>())).ReturnsAsync((UserPreference?)null);
        _repository.Setup(r => r.SaveAsync(It.IsAny<UserPreference>(), It.IsAny<CancellationToken>())).ReturnsAsync(persisted);

        var result = await _service.SaveAsync("u1", "dark", "de-DE", true, CancellationToken.None);

        result.Should().BeSameAs(persisted);
    }

    [Fact]
    public async Task Null_user_id_is_rejected()
    {
        await FluentActions.Awaiting(() => _service.GetOrDefaultAsync(null!, CancellationToken.None)).Should().ThrowAsync<ArgumentNullException>();
        await FluentActions.Awaiting(() => _service.SaveAsync(null!, "dark", "en-US", true, CancellationToken.None)).Should().ThrowAsync<ArgumentNullException>();
    }
}
