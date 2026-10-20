using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using OtterWorks.Desktop.Models;
using OtterWorks.Desktop.Services;
using Xunit;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>
    /// Pins DPAPI session persistence (including a session file in the shape the
    /// .NET Framework 4.8 build wrote) and appsettings.json loading. Both touch files
    /// outside the test, so they share one non-parallel collection and restore what
    /// was there before.
    /// </summary>
    [Collection("files")]
    public class SessionAndSettingsTests : IDisposable
    {
        private static readonly string SessionPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "OtterWorks", "session.dat");

        private static readonly string SettingsPath =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "appsettings.json");

        private readonly byte[] _sessionBackup;
        private readonly byte[] _settingsBackup;

        public SessionAndSettingsTests()
        {
            _sessionBackup = File.Exists(SessionPath) ? File.ReadAllBytes(SessionPath) : null;
            _settingsBackup = File.Exists(SettingsPath) ? File.ReadAllBytes(SettingsPath) : null;
        }

        public void Dispose()
        {
            Restore(SessionPath, _sessionBackup);
            Restore(SettingsPath, _settingsBackup);
        }

        [Fact]
        public void Persisted_session_round_trips_and_is_not_plaintext()
        {
            var first = new SessionState(true);
            first.SetSession(new AuthResponse
            {
                AccessToken = "persisted-token",
                RefreshToken = "ref.persist",
                User = new AuthUser { Id = "u-9", Email = "kim@example.com", DisplayName = "Kim" },
            });

            string onDisk = Encoding.UTF8.GetString(File.ReadAllBytes(SessionPath));
            Assert.DoesNotContain("persisted-token", onDisk);

            var second = new SessionState(true);
            Assert.True(second.TryRestore());
            Assert.Equal("persisted-token", second.AccessToken);
            Assert.Equal("ref.persist", second.RefreshToken);
            Assert.Equal("u-9", second.User.Id);
            Assert.Equal("kim@example.com", second.User.Email);
            Assert.Equal("Kim", second.User.DisplayName);

            second.Clear();
            Assert.False(File.Exists(SessionPath));
            Assert.False(second.IsAuthenticated);
        }

        [Fact]
        public void Session_file_written_by_the_net48_build_still_restores()
        {
            const string legacyJson =
                "{\"AccessToken\":\"acc.legacy\",\"RefreshToken\":\"ref.legacy\"," +
                "\"User\":{\"id\":\"u-48\",\"email\":\"old@example.com\",\"displayName\":\"Old Build\"}}";
            Directory.CreateDirectory(Path.GetDirectoryName(SessionPath));
            File.WriteAllBytes(SessionPath, ProtectedData.Protect(
                Encoding.UTF8.GetBytes(legacyJson), null, DataProtectionScope.CurrentUser));

            var session = new SessionState(true);

            Assert.True(session.TryRestore());
            Assert.Equal("acc.legacy", session.AccessToken);
            Assert.Equal("u-48", session.User.Id);
            Assert.Equal("Old Build", session.User.DisplayName);
        }

        [Fact]
        public void Corrupt_session_file_is_discarded()
        {
            Directory.CreateDirectory(Path.GetDirectoryName(SessionPath));
            File.WriteAllBytes(SessionPath, new byte[] { 1, 2, 3, 4 });

            Assert.False(new SessionState(true).TryRestore());
            Assert.False(File.Exists(SessionPath));
        }

        [Fact]
        public void Session_is_not_restored_when_persistence_is_off()
        {
            new SessionState(true).SetSession(new AuthResponse { AccessToken = "acc.x", User = new AuthUser() });

            Assert.False(new SessionState(false).TryRestore());
        }

        [Fact]
        public void Settings_are_read_from_appsettings_json()
        {
            File.WriteAllText(SettingsPath, "{\"apiBaseUrl\":\"http://gateway.test:9000/api/v1\",\"persistTokens\":true}");

            AppSettings s = AppSettings.Load();

            Assert.Equal("http://gateway.test:9000/api/v1", s.ApiBaseUrl);
            Assert.True(s.PersistTokens);
        }

        [Theory]
        [InlineData("not json")]
        [InlineData("{\"apiBaseUrl\":\"  \",\"persistTokens\":true}")]
        [InlineData("null")]
        public void Bad_settings_fall_back_to_defaults(string content)
        {
            File.WriteAllText(SettingsPath, content);

            AppSettings s = AppSettings.Load();

            Assert.Equal("http://localhost:8080/api/v1", s.ApiBaseUrl);
            Assert.False(s.PersistTokens);
        }

        [Fact]
        public void Missing_settings_fall_back_to_defaults()
        {
            File.Delete(SettingsPath);

            Assert.Equal("http://localhost:8080/api/v1", AppSettings.Load().ApiBaseUrl);
        }

        private static void Restore(string path, byte[] backup)
        {
            if (backup == null)
            {
                File.Delete(path);
            }
            else
            {
                File.WriteAllBytes(path, backup);
            }
        }
    }
}
