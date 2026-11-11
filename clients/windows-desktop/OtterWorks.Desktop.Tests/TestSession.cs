using OtterWorks.Desktop.Models;
using OtterWorks.Desktop.Services;
using OtterWorks.Desktop.ViewModels;

namespace OtterWorks.Desktop.Tests
{
    internal static class TestSession
    {
        public const string Email = "alex@example.com";

        public static MainViewModel SignedIn(StubHttpHandler handler, out SessionState session)
        {
            session = new SessionState(persist: false);
            session.SetSession(new AuthResponse
            {
                AccessToken = "test-access-token",
                RefreshToken = "test-refresh-token",
                User = new AuthUser { Id = "user-1", Email = Email, DisplayName = "Alex Rivera" },
            });

            var settings = new AppSettings { ApiBaseUrl = "http://gateway.test/api/v1" };
            var api = new OtterWorksApiClient(settings, session, handler);
            return new MainViewModel(api, session);
        }
    }
}
