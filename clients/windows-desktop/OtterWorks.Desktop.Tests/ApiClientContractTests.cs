using System;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using OtterWorks.Desktop.Models;
using OtterWorks.Desktop.Services;
using Xunit;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>
    /// Pins the wire contract of <see cref="OtterWorksApiClient"/>: camelCase auth payloads,
    /// snake_case document and file payloads, the exact request bodies, paging query strings
    /// and bearer header, and how error replies become <see cref="ApiException"/> messages.
    /// </summary>
    public class ApiClientContractTests
    {
        private const string AuthJson =
            "{\"accessToken\":\"acc.123\",\"refreshToken\":\"ref.456\",\"tokenType\":\"Bearer\"," +
            "\"expiresIn\":3600,\"user\":{\"id\":\"u-1\",\"email\":\"zoe+desk@example.com\"," +
            "\"displayName\":\"Zo\u00eb O'Brien\"},\"unknownField\":{\"nested\":[1,2]}}";

        private const string DocumentJson =
            "{\"id\":\"d-1\",\"title\":\"Q3 <draft> & notes\",\"content\":\"hello world\"," +
            "\"content_type\":\"text/plain\",\"owner_id\":\"u-1\",\"folder_id\":null,\"is_deleted\":false," +
            "\"word_count\":2,\"version\":3,\"created_at\":\"2026-10-20T06:26:30.883Z\"," +
            "\"updated_at\":\"2026-10-20T08:15:00.123456+02:00\",\"tags\":[\"x\"]}";

        private static OtterWorksApiClient Client(RecordingServer server, string token = null)
        {
            var session = new SessionState(false);
            if (token != null)
            {
                session.SetSession(new AuthResponse { AccessToken = token, User = new AuthUser { Id = "u-1" } });
            }

            return new OtterWorksApiClient(new AppSettings { ApiBaseUrl = server.BaseUrl + "/" }, session);
        }

        private static void AssertAuth(AuthResponse r)
        {
            Assert.Equal("acc.123", r.AccessToken);
            Assert.Equal("ref.456", r.RefreshToken);
            Assert.Equal("Bearer", r.TokenType);
            Assert.Equal(3600L, r.ExpiresIn);
            Assert.Equal("u-1", r.User.Id);
            Assert.Equal("zoe+desk@example.com", r.User.Email);
            Assert.Equal("Zo\u00eb O'Brien", r.User.DisplayName);
        }

        [Fact]
        public async Task Register_posts_camelCase_body_without_bearer_and_reads_camelCase_reply()
        {
            using (var server = new RecordingServer(201, AuthJson))
            {
                AuthResponse r = await Client(server, "stale").RegisterAsync("Zo\u00eb O'Brien", "zoe+desk@example.com", "p@ss<word>1");

                AssertAuth(r);
                RecordedRequest req = server.Requests.Single();
                Assert.Equal("POST", req.Method);
                Assert.Equal("/api/v1/auth/register", req.Path);
                Assert.Null(req.Authorization);
                Assert.Equal("application/json; charset=utf-8", req.ContentType);
                Assert.Equal(
                    "{\"displayName\":\"Zo\u00eb O'Brien\",\"email\":\"zoe+desk@example.com\",\"password\":\"p@ss<word>1\"}",
                    req.Body);
            }
        }

        [Fact]
        public async Task Login_posts_email_and_password_only()
        {
            using (var server = new RecordingServer(200, AuthJson))
            {
                AuthResponse r = await Client(server).LoginAsync("zoe+desk@example.com", "secret-pass");

                AssertAuth(r);
                RecordedRequest req = server.Requests.Single();
                Assert.Equal("/api/v1/auth/login", req.Path);
                Assert.Null(req.Authorization);
                Assert.Equal("{\"email\":\"zoe+desk@example.com\",\"password\":\"secret-pass\"}", req.Body);
            }
        }

        [Fact]
        public async Task GetDocuments_sends_bearer_and_paging_and_reads_snake_case()
        {
            string page = "{\"items\":[" + DocumentJson + "],\"total\":7,\"page\":2,\"size\":5,\"pages\":2}";
            using (var server = new RecordingServer(200, page))
            {
                DocumentListResponse r = await Client(server, "tok-1").GetDocumentsAsync(2, 5);

                RecordedRequest req = server.Requests.Single();
                Assert.Equal("GET", req.Method);
                Assert.Equal("/api/v1/documents", req.Path);
                Assert.Equal("?page=2&size=5", req.Query);
                Assert.Equal("Bearer tok-1", req.Authorization);
                Assert.Equal(7, r.Total);
                Assert.Equal(2, r.Page);
                Assert.Equal(5, r.Size);
                Assert.Equal(2, r.Pages);
                AssertDocument(r.Items.Single());
            }
        }

        [Fact]
        public async Task GetDocuments_defaults_to_first_page_of_fifty()
        {
            using (var server = new RecordingServer(200, "{\"items\":[],\"total\":0,\"page\":1,\"size\":50,\"pages\":0}"))
            {
                DocumentListResponse r = await Client(server, "tok-1").GetDocumentsAsync();

                Assert.Equal("?page=1&size=50", server.Requests.Single().Query);
                Assert.Empty(r.Items);
            }
        }

        [Fact]
        public async Task CreateDocument_posts_title_with_bearer_and_reads_created_document()
        {
            using (var server = new RecordingServer(201, DocumentJson))
            {
                Document d = await Client(server, "tok-2").CreateDocumentAsync("Q3 <draft> & notes");

                RecordedRequest req = server.Requests.Single();
                Assert.Equal("POST", req.Method);
                Assert.Equal("/api/v1/documents", req.Path);
                Assert.Equal("Bearer tok-2", req.Authorization);
                Assert.Equal("{\"title\":\"Q3 <draft> & notes\"}", req.Body);
                AssertDocument(d);
            }
        }

        [Fact]
        public async Task GetFiles_sends_page_size_and_reads_snake_case()
        {
            string body = "{\"files\":[{\"id\":\"f-1\",\"name\":\"site-photo.jpg\",\"size\":1048576," +
                          "\"content_type\":\"image/jpeg\",\"created_at\":\"2026-10-02T14:05:12Z\"}," +
                          "{\"id\":\"f-2\",\"name\":\"empty.bin\",\"size\":null,\"content_type\":null,\"created_at\":null}]," +
                          "\"total\":2,\"page\":1,\"page_size\":50}";
            using (var server = new RecordingServer(200, body))
            {
                FileListResponse r = await Client(server, "tok-3").GetFilesAsync();

                RecordedRequest req = server.Requests.Single();
                Assert.Equal("/api/v1/files", req.Path);
                Assert.Equal("?page=1&page_size=50", req.Query);
                Assert.Equal("Bearer tok-3", req.Authorization);
                Assert.Equal(2, r.Total);
                Assert.Equal(50, r.PageSize);
                FileItem f = r.Files[0];
                Assert.Equal("f-1", f.Id);
                Assert.Equal("site-photo.jpg", f.Name);
                Assert.Equal(1048576L, f.Size);
                Assert.Equal("image/jpeg", f.ContentType);
                Assert.Equal(new DateTimeOffset(2026, 10, 2, 14, 5, 12, TimeSpan.Zero), f.CreatedAt);
                Assert.Null(r.Files[1].Size);
                Assert.Null(r.Files[1].CreatedAt);
            }
        }

        private static void AssertDocument(Document d)
        {
            Assert.Equal("d-1", d.Id);
            Assert.Equal("Q3 <draft> & notes", d.Title);
            Assert.Equal("hello world", d.Content);
            Assert.Equal("text/plain", d.ContentType);
            Assert.Equal("u-1", d.OwnerId);
            Assert.Null(d.FolderId);
            Assert.False(d.IsDeleted);
            Assert.Equal(2, d.WordCount);
            Assert.Equal(3, d.Version);
            Assert.Equal(new DateTimeOffset(2026, 10, 20, 6, 26, 30, 883, TimeSpan.Zero), d.CreatedAt);
            Assert.Equal(TimeSpan.FromHours(2), d.UpdatedAt.Value.Offset);
            Assert.Equal(new DateTimeOffset(2026, 10, 20, 8, 15, 0, TimeSpan.FromHours(2)).AddTicks(1234560), d.UpdatedAt);
        }
    }
}
