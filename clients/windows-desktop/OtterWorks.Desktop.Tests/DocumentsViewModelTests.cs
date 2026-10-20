using System;
using System.Net;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OtterWorks.Desktop.Services;
using OtterWorks.Desktop.ViewModels;
using OtterWorks.Desktop.Views;

namespace OtterWorks.Desktop.Tests
{
    [TestClass]
    public class DocumentsViewModelTests
    {
        private const string EmptyDocuments = "{\"items\":[],\"total\":0,\"page\":1,\"size\":50,\"pages\":0}";

        private const string OneDocument =
            "{\"items\":[{\"id\":\"d1\",\"title\":\"Partner onboarding checklist\",\"word_count\":0,\"version\":1}]," +
            "\"total\":1,\"page\":1,\"size\":50,\"pages\":1}";

        // Shape returned by the file service: mime_type and size_bytes.
        private const string ThreeFiles =
            "{\"files\":[" +
            "{\"id\":\"f1\",\"name\":\"Quarterly report.pdf\",\"mime_type\":\"application/pdf\",\"size_bytes\":482113," +
            "\"owner_id\":\"user-1\",\"version\":1,\"is_trashed\":false,\"created_at\":\"2026-10-14T19:30:00Z\"}," +
            "{\"id\":\"f2\",\"name\":\"Team photo.png\",\"mime_type\":\"image/png\",\"size_bytes\":1830442," +
            "\"owner_id\":\"user-1\",\"version\":1,\"is_trashed\":false,\"created_at\":\"2026-10-14T19:30:00Z\"}," +
            "{\"id\":\"f3\",\"name\":\"Budget.xlsx\",\"mime_type\":\"text/csv\",\"size_bytes\":512," +
            "\"owner_id\":\"user-1\",\"version\":1,\"is_trashed\":false,\"created_at\":\"2026-10-14T19:30:00Z\"}]," +
            "\"total\":3,\"page\":1,\"page_size\":50}";

        private const string ExpiredToken = "{\"error\":\"invalid token: token has invalid claims: token is expired\"}";

        [TestMethod]
        public async Task LoadFiles_SwitchesToFilesView_AndReadsFileServiceFields()
        {
            var handler = new StubHttpHandler()
                .On("/documents", HttpStatusCode.OK, OneDocument)
                .On("/files", HttpStatusCode.OK, ThreeFiles);
            MainViewModel main = TestSession.SignedIn(handler, out _);
            var vm = (DocumentsViewModel)main.CurrentViewModel;
            await vm.InitialLoad;

            await vm.LoadFilesAsync();

            Assert.IsTrue(vm.IsShowingFiles);
            Assert.IsFalse(vm.IsShowingDocuments);
            Assert.AreEqual("Files", vm.Heading);
            Assert.AreEqual(3, vm.Files.Count);
            Assert.AreEqual("Quarterly report.pdf", vm.Files[0].Name);
            Assert.AreEqual("application/pdf", vm.Files[0].ContentType);
            Assert.AreEqual(482113L, vm.Files[0].Size);
            Assert.AreEqual("512 B", vm.Files[2].SizeDisplay);
            Assert.IsFalse(vm.IsEmpty, "The documents empty state must not show over the files list.");
            Assert.IsFalse(vm.IsFilesEmpty);

            await vm.ShowDocumentsAsync();

            Assert.IsFalse(vm.IsShowingFiles);
            Assert.AreEqual("Documents", vm.Heading);
            Assert.AreEqual(1, vm.Documents.Count);
        }

        [TestMethod]
        public async Task LoadFiles_WithNoFiles_ShowsFilesEmptyStateOnly()
        {
            var handler = new StubHttpHandler()
                .On("/documents", HttpStatusCode.OK, EmptyDocuments)
                .On("/files", HttpStatusCode.OK, "{\"files\":[],\"total\":0,\"page\":1,\"page_size\":50}");
            MainViewModel main = TestSession.SignedIn(handler, out _);
            var vm = (DocumentsViewModel)main.CurrentViewModel;
            await vm.InitialLoad;
            Assert.IsTrue(vm.IsEmpty);

            await vm.LoadFilesAsync();

            Assert.IsTrue(vm.IsFilesEmpty);
            Assert.IsFalse(vm.IsEmpty);
        }

        [TestMethod]
        public async Task DocumentsView_ShowsFilesListInFilesMode()
        {
            var handler = new StubHttpHandler()
                .On("/documents", HttpStatusCode.OK, OneDocument)
                .On("/files", HttpStatusCode.OK, ThreeFiles);
            MainViewModel main = TestSession.SignedIn(handler, out _);
            var vm = (DocumentsViewModel)main.CurrentViewModel;
            await vm.InitialLoad;
            await vm.LoadFilesAsync();

            RunOnStaThread(() =>
            {
                EnsureApplicationResources();
                var view = new DocumentsView { DataContext = vm };
                view.Measure(new Size(960, 600));
                view.Arrange(new Rect(0, 0, 960, 600));
                view.Dispatcher.Invoke(() => { }, DispatcherPriority.DataBind);

                var filesList = view.FindName("FilesList") as ListBox;
                var documentsList = view.FindName("DocumentsList") as ListBox;
                Assert.IsNotNull(filesList, "DocumentsView has no list bound to the files collection.");
                Assert.AreSame(vm.Files, filesList.ItemsSource, "ItemsSource: " + (filesList.ItemsSource?.GetType().FullName ?? "null") + " DataContext: " + (view.DataContext?.GetType().Name ?? "null"));
                Assert.AreEqual(Visibility.Visible, ((FrameworkElement)filesList.Parent).Visibility);
                Assert.AreEqual(Visibility.Collapsed, documentsList.Visibility);
                Assert.AreEqual(3, filesList.Items.Count);
            });
        }

        [TestMethod]
        public async Task ExpiredToken_OnRefresh_ReturnsToSignInWithExpiryMessage()
        {
            var handler = new StubHttpHandler()
                .On("/documents", HttpStatusCode.OK, OneDocument)
                .On("/documents", HttpStatusCode.Unauthorized, ExpiredToken);
            MainViewModel main = TestSession.SignedIn(handler, out SessionState session);
            var vm = (DocumentsViewModel)main.CurrentViewModel;
            await vm.InitialLoad;

            await vm.ShowDocumentsAsync();

            var login = main.CurrentViewModel as LoginViewModel;
            Assert.IsNotNull(login, "An expired session must return the user to sign in.");
            Assert.AreEqual(MainViewModel.SessionExpiredMessage, login.ErrorMessage);
            Assert.AreEqual(TestSession.Email, login.Email);
            Assert.IsFalse(session.IsAuthenticated);
            Assert.IsFalse(main.IsAuthenticated);
        }

        [TestMethod]
        public async Task ExpiredToken_OnFiles_ReturnsToSignIn()
        {
            var handler = new StubHttpHandler()
                .On("/documents", HttpStatusCode.OK, OneDocument)
                .On("/files", HttpStatusCode.Unauthorized, ExpiredToken);
            MainViewModel main = TestSession.SignedIn(handler, out SessionState session);
            var vm = (DocumentsViewModel)main.CurrentViewModel;
            await vm.InitialLoad;

            await vm.LoadFilesAsync();

            Assert.IsInstanceOfType(main.CurrentViewModel, typeof(LoginViewModel));
            Assert.IsFalse(session.IsAuthenticated);
        }

        [TestMethod]
        public async Task ServerError_StaysOnDocumentsWithMessage()
        {
            var handler = new StubHttpHandler()
                .On("/documents", HttpStatusCode.OK, OneDocument)
                .On("/documents", HttpStatusCode.InternalServerError, "{\"message\":\"Internal error\"}");
            MainViewModel main = TestSession.SignedIn(handler, out SessionState session);
            var vm = (DocumentsViewModel)main.CurrentViewModel;
            await vm.InitialLoad;

            await vm.ShowDocumentsAsync();

            Assert.AreSame(vm, main.CurrentViewModel);
            Assert.AreEqual("Internal error", vm.ErrorMessage);
            Assert.IsTrue(session.IsAuthenticated);
        }

        private static void EnsureApplicationResources()
        {
            if (Application.Current == null)
            {
                var app = new App();
                app.InitializeComponent();
            }
        }

        private static void RunOnStaThread(Action action)
        {
            Exception failure = null;
            var thread = new Thread(() =>
            {
                try
                {
                    action();
                }
                catch (Exception ex)
                {
                    failure = ex;
                }
            });
            thread.SetApartmentState(ApartmentState.STA);
            thread.Start();
            thread.Join();
            if (failure != null)
            {
                throw new AssertFailedException(failure.Message, failure);
            }
        }
    }
}
