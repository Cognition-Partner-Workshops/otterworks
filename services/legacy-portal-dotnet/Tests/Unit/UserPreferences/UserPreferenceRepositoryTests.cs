using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.UserPreferences.Data;
using OtterWorks.LegacyPortal.UserPreferences.Models;

namespace OtterWorks.LegacyPortal.Tests.Unit.UserPreferences;

public class UserPreferenceRepositoryTests
{
    private readonly DbContextOptions<UserPreferencesDbContext> _options = new DbContextOptionsBuilder<UserPreferencesDbContext>()
        .UseInMemoryDatabase($"prefs-repo-{Guid.NewGuid():N}")
        .Options;

    [Fact]
    public async Task Save_inserts_new_entity_and_find_returns_it()
    {
        await using (var context = new UserPreferencesDbContext(_options))
        {
            var saved = await new UserPreferenceRepository(context).SaveAsync(new UserPreference("u1", "dark", "fr-FR", false), CancellationToken.None);
            saved.UserId.Should().Be("u1");
        }

        await using (var context = new UserPreferencesDbContext(_options))
        {
            var found = await new UserPreferenceRepository(context).FindByIdAsync("u1", CancellationToken.None);
            found.Should().BeEquivalentTo(new { UserId = "u1", Theme = "dark", Locale = "fr-FR", EmailNotifications = false });
        }
    }

    [Fact]
    public async Task Find_returns_null_when_missing()
    {
        await using var context = new UserPreferencesDbContext(_options);

        (await new UserPreferenceRepository(context).FindByIdAsync("missing", CancellationToken.None)).Should().BeNull();
    }

    [Fact]
    public async Task Save_of_detached_entity_with_existing_id_merges_into_managed_row()
    {
        await using (var context = new UserPreferencesDbContext(_options))
        {
            await new UserPreferenceRepository(context).SaveAsync(new UserPreference("u1", "dark", "fr-FR", false), CancellationToken.None);
        }

        await using (var context = new UserPreferencesDbContext(_options))
        {
            var repository = new UserPreferenceRepository(context);
            var managed = await repository.FindByIdAsync("u1", CancellationToken.None);
            var detached = new UserPreference("u1", "light", "en-GB", true);

            var saved = await repository.SaveAsync(detached, CancellationToken.None);

            saved.Should().BeSameAs(managed);
            saved.Theme.Should().Be("light");
            saved.Locale.Should().Be("en-GB");
            saved.EmailNotifications.Should().BeTrue();
        }

        await using (var context = new UserPreferencesDbContext(_options))
        {
            (await context.Preferences.CountAsync()).Should().Be(1);
            (await context.Preferences.SingleAsync()).Theme.Should().Be("light");
        }
    }

    [Fact]
    public void Model_maps_to_user_preferences_schema_with_snake_case_columns()
    {
        using var context = new UserPreferencesDbContext(_options);
        var entity = context.Model.FindEntityType(typeof(UserPreference))!;

        entity.GetSchema().Should().Be("user_preferences");
        entity.GetTableName().Should().Be("user_preference");
        entity.FindPrimaryKey()!.Properties.Select(p => p.Name).Should().Equal(nameof(UserPreference.UserId));
        var columns = entity.GetProperties().ToDictionary(p => p.Name, p => (p.GetColumnName(), p.GetMaxLength(), p.IsNullable));
        columns[nameof(UserPreference.UserId)].Should().Be(("user_id", 100, false));
        columns[nameof(UserPreference.Theme)].Should().Be(("theme", 20, false));
        columns[nameof(UserPreference.Locale)].Should().Be(("locale", 20, false));
        columns[nameof(UserPreference.EmailNotifications)].Should().Be(("email_notifications", (int?)null, false));
    }

    [Fact]
    public async Task Schema_initializer_is_a_no_op_on_in_memory_provider()
    {
        await using var context = new UserPreferencesDbContext(_options);

        await new UserPreferencesSchemaInitializer(context).InitializeAsync(CancellationToken.None);

        (await context.Preferences.CountAsync()).Should().Be(0);
    }
}
