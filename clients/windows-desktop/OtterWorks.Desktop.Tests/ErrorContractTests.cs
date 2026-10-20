using System.Net;
using System.Threading.Tasks;
using OtterWorks.Desktop.Models;
using OtterWorks.Desktop.Services;
using Xunit;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>Pins how non-success and malformed replies surface to the views.</summary>
    public class ErrorContractTests
    {
        private static OtterWorksApiClient Client(string baseUrl)
        {
            return new OtterWorksApiClient(new AppSettings { ApiBaseUrl = baseUrl }, new SessionState(false));
        }

        [Theory]
        [InlineData("{\"message\":\"Invalid email or password\",\"error\":\"ignored\"}", "Invalid email or password")]
        [InlineData("{\"error\":\"missing or invalid bearer token\",\"detail\":\"ignored\"}", "missing or invalid bearer token")]
        [InlineData("{\"message\":null,\"detail\":\"title is required\"}", "title is required")]
        [InlineData("{\"detail\":[{\"loc\":[\"body\",\"title\"],\"msg\":\"field required\"}]}", "[\r\n  {\r\n    \"loc\": [\r\n      \"body\",\r\n      \"title\"\r\n    ],\r\n    \"msg\": \"field required\"\r\n  }\r\n]")]
        [InlineData("{\"message\":42}", "42")]
        [InlineData("{\"status\":\"down\"}", "{\"status\":\"down\"}")]
        [InlineData("[\"a\"]", "[\"a\"]")]
        [InlineData("upstream connect error", "upstream connect error")]
        public async Task Error_reply_becomes_ApiException_with_first_known_field(string body, string expected)
        {
            using (var server = new RecordingServer(401, body))
            {
                ApiException ex = await Assert.ThrowsAsync<ApiException>(
                    () => Client(server.BaseUrl).LoginAsync("a@example.com", "password1"));

                Assert.Equal(HttpStatusCode.Unauthorized, ex.StatusCode);
                Assert.Equal(expected, ex.Message);
            }
        }

        [Fact]
        public async Task Empty_error_reply_names_the_status()
        {
            using (var server = new RecordingServer(404, null))
            {
                ApiException ex = await Assert.ThrowsAsync<ApiException>(() => Client(server.BaseUrl).GetFilesAsync());

                Assert.Equal(HttpStatusCode.NotFound, ex.StatusCode);
                Assert.Equal("Request failed with status 404 (NotFound).", ex.Message);
            }
        }

        [Fact]
        public async Task Non_json_success_reply_is_reported_as_unexpected()
        {
            using (var server = new RecordingServer(200, "<html>gateway</html>"))
            {
                ApiException ex = await Assert.ThrowsAsync<ApiException>(() => Client(server.BaseUrl).GetDocumentsAsync());

                Assert.Equal(HttpStatusCode.OK, ex.StatusCode);
                Assert.Equal("The OtterWorks backend returned an unexpected (non-JSON) response.", ex.Message);
            }
        }

        [Fact]
        public async Task Empty_success_reply_returns_null()
        {
            using (var server = new RecordingServer(204, null))
            {
                Document created = await Client(server.BaseUrl).CreateDocumentAsync("x");

                Assert.Null(created);
            }
        }

        [Fact]
        public async Task Unreachable_backend_is_reported_with_status_zero()
        {
            int port = RecordingServer.FreePort();
            ApiException ex = await Assert.ThrowsAsync<ApiException>(
                () => Client("http://127.0.0.1:" + port + "/api/v1").LoginAsync("a@example.com", "password1"));

            Assert.Equal((HttpStatusCode)0, ex.StatusCode);
            Assert.StartsWith(
                "Could not reach the OtterWorks backend. Verify it is running and that the API base URL is correct.\n\n",
                ex.Message);
        }
    }
}
