using System;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OtterWorks.Desktop.Services;
using OtterWorks.Desktop.ViewModels;

namespace OtterWorks.Desktop.Tests
{
    /// <summary>
    /// Covers the two walk-through fixes: the Files button must show the files it loads, and a
    /// failed load must never be presented as an empty list.
    /// </summary>
    [TestClass]
    public class DocumentsViewModelTests
    {
        private const string EmptyDocuments = "{\"items\":[],\"total\":0,\"page\":1,\"size\":50,\"pages\":0}";

        private const string TwoFiles =
            "{\"files\":[" +
            "{\"id\":\"f1\",\"name\":\"Architecture overview.pdf\",\"mime_type\":\"application/pdf\",\"size_bytes\":48213,\"created_at\":\"2026-11-11T10:00:00Z\"}," +
            "{\"id\":\"f2\",\"name\":\"usage.csv\",\"mime_type\":\"text/csv\",\"size_bytes\":900,\"created_at\":\"2026-11-11T10:00:00Z\"}]," +
            "\"total\":2,\"page\":1,\"page_size\":50}";

        private const string NoFiles = "{\"files\":[],\"total\":0,\"page\":1,\"page_size\":50}";

        private const string GatewayDown = "{\"error\":\"service unavailable\",\"target\":\"/api/v1/documents\"}";

        [TestMethod]
        public async Task LoadFiles_SwitchesToFilesViewAndListsEveryFile()
        {
            DocumentsViewModel vm = await CreateAsync(Route(EmptyDocuments, TwoFiles));

            await vm.LoadFilesAsync();

            Assert.IsTrue(vm.IsShowingFiles);
            Assert.IsFalse(vm.IsShowingDocuments);
            Assert.AreEqual("Files", vm.Heading);
            Assert.AreEqual(2, vm.Files.Count);
            Assert.AreEqual("Architecture overview.pdf", vm.Files[0].Name);
            Assert.AreEqual("47 KB", vm.Files[0].SizeText);
            Assert.AreEqual("application/pdf", vm.Files[0].ContentType);
            Assert.IsFalse(vm.IsEmpty, "The documents empty state must not show over the files list.");
            Assert.IsFalse(vm.IsFilesEmpty);
            Assert.AreEqual("2 file(s).", vm.StatusMessage);
        }

        [TestMethod]
        public async Task LoadFiles_NoFiles_ShowsFilesEmptyState()
        {
            DocumentsViewModel vm = await CreateAsync(Route(EmptyDocuments, NoFiles));

            await vm.LoadFilesAsync();

            Assert.IsTrue(vm.IsFilesEmpty);
            Assert.IsFalse(vm.IsEmpty);
        }

        [TestMethod]
        public async Task ShowDocuments_AfterFiles_ReturnsToDocumentsView()
        {
            DocumentsViewModel vm = await CreateAsync(Route(EmptyDocuments, TwoFiles));
            await vm.LoadFilesAsync();

            await vm.LoadDocumentsAsync();

            Assert.IsTrue(vm.IsShowingDocuments);
            Assert.AreEqual("Documents", vm.Heading);
            Assert.IsTrue(vm.IsEmpty);
        }

        [TestMethod]
        public async Task LoadDocuments_ServiceDown_ShowsFailureInsteadOfEmptyState()
        {
            DocumentsViewModel vm = await CreateAsync(_ => Json(HttpStatusCode.BadGateway, GatewayDown));

            Assert.IsFalse(vm.IsEmpty, "\"No documents yet\" must not be shown when the list could not be loaded.");
            Assert.IsTrue(vm.IsLoadFailed);
            Assert.AreEqual(OtterWorksApiClient.ServiceUnavailableMessage, vm.ErrorMessage);
        }

        [TestMethod]
        public async Task LoadDocuments_BackendUnreachable_ShowsFailureInsteadOfEmptyState()
        {
            DocumentsViewModel vm = await CreateAsync(
                _ => throw new HttpRequestException("An error occurred while sending the request."));

            Assert.IsFalse(vm.IsEmpty);
            Assert.IsTrue(vm.IsLoadFailed);
            Assert.AreEqual(OtterWorksApiClient.BackendUnreachableMessage, vm.ErrorMessage);
        }

        [TestMethod]
        public async Task LoadFiles_ServiceDown_ShowsFailureInsteadOfEmptyState()
        {
            DocumentsViewModel vm = await CreateAsync(request =>
                request.RequestUri.AbsolutePath.EndsWith("/files", StringComparison.Ordinal)
                    ? Json(HttpStatusCode.ServiceUnavailable, GatewayDown)
                    : Json(HttpStatusCode.OK, EmptyDocuments));

            await vm.LoadFilesAsync();

            Assert.IsFalse(vm.IsFilesEmpty);
            Assert.IsTrue(vm.IsLoadFailed);
            Assert.AreEqual(OtterWorksApiClient.ServiceUnavailableMessage, vm.ErrorMessage);
        }

        [TestMethod]
        public async Task LoadDocuments_RecoversAfterServiceComesBack()
        {
            bool down = true;
            DocumentsViewModel vm = await CreateAsync(_ => down
                ? Json(HttpStatusCode.BadGateway, GatewayDown)
                : Json(HttpStatusCode.OK, EmptyDocuments));
            Assert.IsTrue(vm.IsLoadFailed);

            down = false;
            await vm.LoadDocumentsAsync();

            Assert.IsFalse(vm.IsLoadFailed);
            Assert.IsTrue(vm.IsEmpty);
            Assert.IsNull(vm.ErrorMessage);
        }

        private static async Task<DocumentsViewModel> CreateAsync(Func<HttpRequestMessage, HttpResponseMessage> responder)
        {
            OtterWorksApiClient api = TestClients.Create(new FakeHttpMessageHandler(responder));
            var main = new MainViewModel(api, new SessionState(persist: false));
            var vm = new DocumentsViewModel(api, main);
            await vm.InitialLoad;
            return vm;
        }

        private static Func<HttpRequestMessage, HttpResponseMessage> Route(string documentsBody, string filesBody)
        {
            return request => Json(
                HttpStatusCode.OK,
                request.RequestUri.AbsolutePath.EndsWith("/files", StringComparison.Ordinal) ? filesBody : documentsBody);
        }

        private static HttpResponseMessage Json(HttpStatusCode status, string body)
        {
            return new HttpResponseMessage(status) { Content = new StringContent(body, Encoding.UTF8, "application/json") };
        }
    }
}
