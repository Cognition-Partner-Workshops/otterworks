using System.Text.Json;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.UserPreferences.Models;

namespace OtterWorks.LegacyPortal.Tests.Unit.UserPreferences;

public class PreferenceResponseTests
{
    [Fact]
    public void FromEntity_copies_fields_and_serializes_in_java_order()
    {
        var response = PreferenceResponse.FromEntity(new UserPreference("u1", "dark", "fr-FR", false));

        JsonSerializer.Serialize(response, SpringJson.CreateOptions())
            .Should().Be("{\"userId\":\"u1\",\"theme\":\"dark\",\"locale\":\"fr-FR\",\"emailNotifications\":false}");
    }

    [Theory]
    [InlineData("{\"theme\":\"dark\",\"locale\":\"de-DE\",\"emailNotifications\":\"true\"}", true)]
    [InlineData("{\"theme\":\"dark\",\"locale\":\"de-DE\"}", false)]
    [InlineData("{\"theme\":\"dark\",\"locale\":\"de-DE\",\"emailNotifications\":null}", false)]
    [InlineData("{\"theme\":\"dark\",\"locale\":\"de-DE\",\"emailNotifications\":1}", true)]
    public void Request_binds_email_notifications_like_jackson(string json, bool expected)
    {
        var request = JsonSerializer.Deserialize<UpdatePreferenceRequest>(json, SpringJson.CreateOptions())!;

        request.EmailNotifications.Should().Be(expected);
        request.Theme.Should().Be("dark");
    }
}
