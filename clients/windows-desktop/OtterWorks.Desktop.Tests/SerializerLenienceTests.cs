using System;
using System.IO;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using OtterWorks.Desktop.Models;
using OtterWorks.Desktop.Services;
using Xunit;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>
    /// Pins the lenient parsing the client inherited from Json.NET defaults, which a
    /// serializer swap would otherwise silently tighten: case-insensitive member names,
    /// numbers sent as strings, offset-less timestamps, non-ASCII request bodies and
    /// commented settings files.
    /// </summary>
    [Collection("files")]
    public class SerializerLenienceTests
    {
        private static OtterWorksApiClient Client(RecordingServer server)
        {
            return new OtterWorksApiClient(new AppSettings { ApiBaseUrl = server.BaseUrl }, new SessionState(false));
        }

        [Fact]
        public async Task Reply_member_names_match_case_insensitively()
        {
            string body = "{\"AccessToken\":\"acc.upper\",\"EXPIRESIN\":60,\"User\":{\"ID\":\"u-7\",\"DisplayName\":\"Upper\"}}";
            using (var server = new RecordingServer(200, body))
            {
                AuthResponse r = await Client(server).LoginAsync("a@example.com", "pw");

                Assert.Equal("acc.upper", r.AccessToken);
                Assert.Equal(60L, r.ExpiresIn);
                Assert.Equal("u-7", r.User.Id);
                Assert.Equal("Upper", r.User.DisplayName);
            }
        }

        [Fact]
        public async Task Numbers_sent_as_strings_are_accepted()
        {
            string body = "{\"files\":[{\"id\":\"f\",\"size\":\"2048\"}],\"total\":\"1\",\"page\":\"1\",\"page_size\":\"50\"}";
            using (var server = new RecordingServer(200, body))
            {
                FileListResponse r = await Client(server).GetFilesAsync();

                Assert.Equal(1, r.Total);
                Assert.Equal(50, r.PageSize);
                Assert.Equal(2048L, r.Files[0].Size);
            }
        }

        [Fact]
        public async Task Timestamp_without_offset_is_read_as_local_time()
        {
            string body = "{\"id\":\"d\",\"created_at\":\"2026-07-01T09:30:00\"}";
            using (var server = new RecordingServer(201, body))
            {
                Document d = await Client(server).CreateDocumentAsync("t");

                var local = new DateTime(2026, 7, 1, 9, 30, 0, DateTimeKind.Unspecified);
                Assert.Equal(new DateTimeOffset(local, TimeZoneInfo.Local.GetUtcOffset(local)), d.CreatedAt);
            }
        }

        [Fact]
        public async Task Nanosecond_timestamps_round_half_up_to_the_nearest_tick()
        {
            string body = "{\"files\":[{\"id\":\"f\",\"created_at\":\"2026-10-02T14:05:12.123456789Z\"}],\"total\":1}";
            using (var server = new RecordingServer(200, body))
            {
                FileListResponse r = await Client(server).GetFilesAsync();

                Assert.Equal(new DateTimeOffset(2026, 10, 2, 14, 5, 12, TimeSpan.Zero).AddTicks(1234568), r.Files[0].CreatedAt);
            }
        }

        [Theory]
        [InlineData("2026-10-02T14:05:12.12345675Z", 1234568L)]
        [InlineData("2026-10-02T14:05:12.12345665Z", 1234567L)]
        [InlineData("2026-10-02T14:05:12.12345664999Z", 1234566L)]
        [InlineData("2026-10-02T14:05:12.99999995Z", 10000000L)]
        public async Task Sub_tick_digits_round_on_the_eighth_digit(string stamp, long ticksAfterSecond)
        {
            string body = "{\"files\":[{\"id\":\"f\",\"created_at\":\"" + stamp + "\"}],\"total\":1}";
            using (var server = new RecordingServer(200, body))
            {
                FileListResponse r = await Client(server).GetFilesAsync();

                Assert.Equal(new DateTimeOffset(2026, 10, 2, 14, 5, 12, TimeSpan.Zero).AddTicks(ticksAfterSecond), r.Files[0].CreatedAt);
            }
        }

        [Fact]
        public async Task Numeric_ids_are_read_into_string_members()
        {
            string body = "{\"items\":[{\"id\":1042,\"title\":\"t\",\"owner_id\":7,\"version\":1}],\"total\":1}";
            using (var server = new RecordingServer(200, body))
            {
                DocumentListResponse r = await Client(server).GetDocumentsAsync();

                Assert.Equal("1042", r.Items[0].Id);
                Assert.Equal("7", r.Items[0].OwnerId);
            }
        }

        [Fact]
        public async Task Non_ascii_title_is_sent_unescaped()
        {
            using (var server = new RecordingServer(201, "{\"id\":\"d\"}"))
            {
                await Client(server).CreateDocumentAsync("Caf\u00e9 \u2014 \u65e5\u672c \"q\" \u005c tab\t");

                Assert.Equal(
                    "{\"title\":\"Caf\u00e9 \u2014 \u65e5\u672c \u005c\"q\u005c\" \u005c\u005c tab\u005ct\"}",
                    server.Requests.Single().Body);
            }
        }

        [Theory]
        [InlineData("{\"message\":true}", "True")]
        [InlineData("{\"error\":false}", "False")]
        [InlineData("{\"detail\":{\"code\":\"E1\"}}", "{\r\n  \"code\": \"E1\"\r\n}")]
        [InlineData("{\"message\":\"\"}", "")]
        public async Task Error_values_are_rendered_like_the_net48_build(string body, string expected)
        {
            using (var server = new RecordingServer(422, body))
            {
                ApiException ex = await Assert.ThrowsAsync<ApiException>(() => Client(server).GetFilesAsync());

                Assert.Equal((HttpStatusCode)422, ex.StatusCode);
                Assert.Equal(expected, ex.Message);
            }
        }

        [Fact]
        public void Settings_file_may_contain_comments_and_trailing_commas()
        {
            string path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "appsettings.json");
            byte[] backup = File.Exists(path) ? File.ReadAllBytes(path) : null;
            try
            {
                File.WriteAllText(path, "{\n  // local gateway\n  \"apiBaseUrl\": \"http://127.0.0.1:18080/api/v1\",\n  \"persistTokens\": true,\n}");

                AppSettings s = AppSettings.Load();

                Assert.Equal("http://127.0.0.1:18080/api/v1", s.ApiBaseUrl);
                Assert.True(s.PersistTokens);
            }
            finally
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
}
