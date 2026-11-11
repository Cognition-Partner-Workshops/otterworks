using System;
using System.Net;
using System.Net.Http;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OtterWorks.Desktop.Services;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>
    /// Characterization tests: pin the user-facing <see cref="ApiException"/> text the client
    /// produces today for transport failures and the error bodies the backend services return.
    /// </summary>
    [TestClass]
    public class OtterWorksApiClientErrorTests
    {
        [TestMethod]
        public async Task ConnectionFailure_ShowsPlainMessageWithoutTransportDetail()
        {
            var handler = FakeHttpMessageHandler.Throwing(
                new HttpRequestException("An error occurred while sending the request."));
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.GetDocumentsAsync());

            Assert.AreEqual((HttpStatusCode)0, ex.StatusCode);
            Assert.AreEqual(
                "Could not reach the OtterWorks backend. Verify it is running and that the " +
                "API base URL is correct.",
                ex.Message);
        }

        [TestMethod]
        public async Task Timeout_TaskCanceledException_BecomesTimeoutMessageWithStatusZero()
        {
            var handler = FakeHttpMessageHandler.Throwing(new TaskCanceledException());
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.GetDocumentsAsync());

            Assert.AreEqual((HttpStatusCode)0, ex.StatusCode);
            Assert.AreEqual(
                "The request to the OtterWorks backend timed out. Verify the server is " +
                "running and responsive.",
                ex.Message);
        }

        [TestMethod]
        public async Task Login400_AuthServiceBody_UsesMessageFieldOverErrorField()
        {
            var handler = FakeHttpMessageHandler.Returning(
                HttpStatusCode.BadRequest,
                "{\"timestamp\":\"2026-11-11T10:00:00.000+00:00\",\"status\":400,\"error\":\"Bad Request\",\"message\":\"Invalid credentials\"}");
            var client = TestClients.Create(handler, token: null);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.LoginAsync("a@example.com", "wrong-password"));

            Assert.AreEqual(HttpStatusCode.BadRequest, ex.StatusCode);
            Assert.AreEqual("Invalid credentials", ex.Message);
        }

        [TestMethod]
        public async Task Gateway502_ServiceUnavailableBody_ShowsFriendlyUnavailableMessage()
        {
            var handler = FakeHttpMessageHandler.Returning(
                HttpStatusCode.BadGateway,
                "{\"error\":\"service unavailable\",\"target\":\"/api/v1/documents\"}");
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.GetDocumentsAsync());

            Assert.AreEqual(HttpStatusCode.BadGateway, ex.StatusCode);
            Assert.AreEqual(OtterWorksApiClient.ServiceUnavailableMessage, ex.Message);
        }

        [TestMethod]
        public async Task Gateway503_CircuitBreakerBody_ShowsFriendlyUnavailableMessage()
        {
            var handler = FakeHttpMessageHandler.Returning(
                HttpStatusCode.ServiceUnavailable,
                "{\"error\":\"service temporarily unavailable\",\"service\":\"/api/v1/documents\",\"reason\":\"circuit breaker open\"}");
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.GetDocumentsAsync());

            Assert.AreEqual(HttpStatusCode.ServiceUnavailable, ex.StatusCode);
            Assert.AreEqual(OtterWorksApiClient.ServiceUnavailableMessage, ex.Message);
        }

        [TestMethod]
        public async Task Gateway401_MissingAuthBody_UsesErrorFieldAndKeepsStatusCode()
        {
            var handler = FakeHttpMessageHandler.Returning(
                HttpStatusCode.Unauthorized,
                "{\"error\":\"missing or invalid authorization header\"}");
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.GetDocumentsAsync());

            Assert.AreEqual(HttpStatusCode.Unauthorized, ex.StatusCode);
            Assert.AreEqual("missing or invalid authorization header", ex.Message);
        }

        [TestMethod]
        public async Task Validation422_DetailArray_DumpsIndentedRawJsonArray()
        {
            var handler = FakeHttpMessageHandler.Returning(
                (HttpStatusCode)422,
                "{\"detail\":[{\"type\":\"string_too_long\",\"loc\":[\"body\",\"title\"],\"msg\":\"String should have at most 500 characters\",\"input\":\"...\",\"ctx\":{\"max_length\":500}}]}");
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.CreateDocumentAsync(new string('x', 501)));

            string expected = string.Join(
                Environment.NewLine,
                "[",
                "  {",
                "    \"type\": \"string_too_long\",",
                "    \"loc\": [",
                "      \"body\",",
                "      \"title\"",
                "    ],",
                "    \"msg\": \"String should have at most 500 characters\",",
                "    \"input\": \"...\",",
                "    \"ctx\": {",
                "      \"max_length\": 500",
                "    }",
                "  }",
                "]");
            Assert.AreEqual((HttpStatusCode)422, ex.StatusCode);
            Assert.AreEqual(expected, ex.Message);
        }

        [TestMethod]
        public async Task Error401_DetailString_UsesDetailField()
        {
            var handler = FakeHttpMessageHandler.Returning(
                HttpStatusCode.Unauthorized,
                "{\"detail\":\"Not authenticated\"}");
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.GetFilesAsync());

            Assert.AreEqual(HttpStatusCode.Unauthorized, ex.StatusCode);
            Assert.AreEqual("Not authenticated", ex.Message);
        }

        [TestMethod]
        public async Task Success200_NonJsonBody_ReportsUnexpectedResponseWithStatusOk()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.OK, "pong", "text/plain");
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.GetDocumentsAsync());

            Assert.AreEqual(HttpStatusCode.OK, ex.StatusCode);
            Assert.AreEqual("The OtterWorks backend returned an unexpected (non-JSON) response.", ex.Message);
        }

        [TestMethod]
        public async Task Error502_HtmlBody_DoesNotLeakHtmlIntoMessage()
        {
            const string html =
                "<html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>\r\n" +
                "<center><h1>502 Bad Gateway</h1></center>\r\n</body>\r\n</html>\r\n";
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.BadGateway, html, "text/html");
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.GetDocumentsAsync());

            Assert.AreEqual(HttpStatusCode.BadGateway, ex.StatusCode);
            Assert.AreEqual(OtterWorksApiClient.ServiceUnavailableMessage, ex.Message);
        }

        [TestMethod]
        public async Task Error504_GatewayTimeout_ShowsFriendlyUnavailableMessage()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.GatewayTimeout, string.Empty);
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.GetFilesAsync());

            Assert.AreEqual(HttpStatusCode.GatewayTimeout, ex.StatusCode);
            Assert.AreEqual(OtterWorksApiClient.ServiceUnavailableMessage, ex.Message);
        }

        [TestMethod]
        public async Task Error500_EmptyBody_UsesGenericStatusMessage()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.InternalServerError, string.Empty);
            var client = TestClients.Create(handler);

            var ex = await Assert.ThrowsExceptionAsync<ApiException>(() => client.GetDocumentsAsync());

            Assert.AreEqual(HttpStatusCode.InternalServerError, ex.StatusCode);
            Assert.AreEqual("Request failed with status 500 (InternalServerError).", ex.Message);
        }
    }
}
