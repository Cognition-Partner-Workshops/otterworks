using System;
using System.Net;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>Characterization tests for how today's models deserialise real service payloads.</summary>
    [TestClass]
    public class OtterWorksApiClientResponseTests
    {
        private const string FileServiceListBody =
            "{\"files\":[{\"id\":\"3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b\",\"name\":\"a.pdf\"," +
            "\"mime_type\":\"application/pdf\",\"size_bytes\":1234,\"s3_key\":\"k\",\"folder_id\":null," +
            "\"owner_id\":\"9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d\",\"version\":1,\"is_trashed\":false," +
            "\"created_at\":\"2026-11-11T10:00:00Z\",\"updated_at\":\"2026-11-11T10:00:00Z\"}]," +
            "\"total\":1,\"page\":1,\"page_size\":50}";

        [TestMethod]
        public async Task GetFiles_FileServiceShape_MapsAllDisplayedFields()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.OK, FileServiceListBody);
            var client = TestClients.Create(handler);

            var result = await client.GetFilesAsync();

            Assert.AreEqual(1, result.Total);
            Assert.AreEqual(1, result.Page);
            Assert.AreEqual(50, result.PageSize);
            Assert.AreEqual(1, result.Files.Count);
            var file = result.Files[0];
            Assert.AreEqual("3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b", file.Id);
            Assert.AreEqual("a.pdf", file.Name);
            Assert.AreEqual(new DateTimeOffset(2026, 11, 11, 10, 0, 0, TimeSpan.Zero), file.CreatedAt);

            Assert.AreEqual(1234L, file.Size);
            Assert.AreEqual("application/pdf", file.ContentType);
            Assert.AreEqual("1.2 KB", file.SizeText);
        }

        [TestMethod]
        public async Task Login200_CamelCaseAuthBody_Deserialises()
        {
            var handler = FakeHttpMessageHandler.Returning(
                HttpStatusCode.OK,
                "{\"accessToken\":\"at\",\"refreshToken\":\"rt\",\"tokenType\":\"Bearer\",\"expiresIn\":900," +
                "\"user\":{\"id\":\"u1\",\"email\":\"a@example.com\",\"displayName\":\"Ada\"}}");
            var client = TestClients.Create(handler, token: null);

            var result = await client.LoginAsync("a@example.com", "password1");

            Assert.AreEqual("at", result.AccessToken);
            Assert.AreEqual("rt", result.RefreshToken);
            Assert.AreEqual("Bearer", result.TokenType);
            Assert.AreEqual(900L, result.ExpiresIn);
            Assert.AreEqual("u1", result.User.Id);
            Assert.AreEqual("a@example.com", result.User.Email);
            Assert.AreEqual("Ada", result.User.DisplayName);
        }

        [TestMethod]
        public async Task Success200_EmptyBody_ReturnsNull()
        {
            var handler = FakeHttpMessageHandler.Returning(HttpStatusCode.OK, string.Empty);
            var client = TestClients.Create(handler);

            var result = await client.GetDocumentsAsync();

            Assert.IsNull(result);
        }
    }
}
