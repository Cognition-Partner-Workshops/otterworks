using System;
using System.Net;
using System.Net.Http;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>Characterization tests for the shape of requests the client sends today.</summary>
    [TestClass]
    public class OtterWorksApiClientRequestTests
    {
        [TestMethod]
        public async Task GetDocuments_SendsBearerTokenAndPageSizeQuery()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.OK, "{\"items\":[],\"total\":0}");
            var client = TestClients.Create(handler);

            await client.GetDocumentsAsync(page: 2, size: 10);

            var request = handler.Requests[0];
            Assert.AreEqual(HttpMethod.Get, request.Method);
            Assert.AreEqual("http://localhost:8080/api/v1/documents?page=2&size=10", request.Uri.ToString());
            Assert.IsTrue(request.HasAuthorization);
            Assert.AreEqual("Bearer " + TestClients.Token, request.Authorization);
            Assert.IsNull(request.Body);
        }

        [TestMethod]
        public async Task GetDocuments_WithoutToken_SendsNoAuthorizationHeader()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.OK, "{}");
            var client = TestClients.Create(handler, token: null);

            await client.GetDocumentsAsync();

            Assert.IsFalse(handler.Requests[0].HasAuthorization);
            Assert.AreEqual("http://localhost:8080/api/v1/documents?page=1&size=50", handler.Requests[0].Uri.ToString());
        }

        [TestMethod]
        public async Task CreateDocument_PostsTitleJsonWithBearerToken()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.Created, "{\"id\":\"d1\",\"title\":\"Plan\"}");
            var client = TestClients.Create(handler);

            var created = await client.CreateDocumentAsync("Plan");

            var request = handler.Requests[0];
            Assert.AreEqual(HttpMethod.Post, request.Method);
            Assert.AreEqual("http://localhost:8080/api/v1/documents", request.Uri.ToString());
            Assert.AreEqual("Bearer " + TestClients.Token, request.Authorization);
            Assert.AreEqual("{\"title\":\"Plan\"}", request.Body);
            Assert.AreEqual("application/json; charset=utf-8", request.ContentType);
            Assert.AreEqual("d1", created.Id);
        }

        [TestMethod]
        public async Task Login_NeverSendsAuthorizationEvenWhenTokenIsHeld()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.OK, "{\"accessToken\":\"new\"}");
            var client = TestClients.Create(handler);

            await client.LoginAsync("a@example.com", "password1");

            var request = handler.Requests[0];
            Assert.AreEqual(HttpMethod.Post, request.Method);
            Assert.AreEqual("http://localhost:8080/api/v1/auth/login", request.Uri.ToString());
            Assert.IsFalse(request.HasAuthorization);
            Assert.AreEqual("{\"email\":\"a@example.com\",\"password\":\"password1\"}", request.Body);
            Assert.AreEqual("application/json; charset=utf-8", request.ContentType);
        }

        [TestMethod]
        public async Task Register_PostsCamelCaseBodyWithoutAuthorization()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.Created, "{\"accessToken\":\"new\"}");
            var client = TestClients.Create(handler);

            await client.RegisterAsync("Ada", "a@example.com", "password1");

            var request = handler.Requests[0];
            Assert.AreEqual("http://localhost:8080/api/v1/auth/register", request.Uri.ToString());
            Assert.IsFalse(request.HasAuthorization);
            Assert.AreEqual(
                "{\"displayName\":\"Ada\",\"email\":\"a@example.com\",\"password\":\"password1\"}",
                request.Body);
        }

        [TestMethod]
        public async Task GetFiles_SendsBearerTokenAndPagePageSizeQuery()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.OK, "{\"files\":[]}");
            var client = TestClients.Create(handler);

            await client.GetFilesAsync(page: 3, pageSize: 25);

            var request = handler.Requests[0];
            Assert.AreEqual(HttpMethod.Get, request.Method);
            Assert.AreEqual("http://localhost:8080/api/v1/files?page=3&page_size=25", request.Uri.ToString());
            Assert.AreEqual("Bearer " + TestClients.Token, request.Authorization);
        }

        [TestMethod]
        public async Task BaseUrl_TrailingSlashIsTrimmed()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.OK, "{}");
            var client = TestClients.Create(handler, baseUrl: "http://gateway.test/api/v1/");

            await client.GetDocumentsAsync();

            Assert.AreEqual("http://gateway.test/api/v1/documents?page=1&size=50", handler.Requests[0].Uri.ToString());
        }
    }
}

