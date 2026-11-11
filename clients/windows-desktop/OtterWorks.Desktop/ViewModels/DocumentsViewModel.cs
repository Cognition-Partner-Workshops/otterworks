using System.Collections.ObjectModel;
using System.Net;
using System.Threading.Tasks;
using System.Windows.Input;
using OtterWorks.Desktop.Models;
using OtterWorks.Desktop.Mvvm;
using OtterWorks.Desktop.Services;

namespace OtterWorks.Desktop.ViewModels
{
    public class DocumentsViewModel : ObservableObject
    {
        private readonly OtterWorksApiClient _api;
        private readonly MainViewModel _main;

        private string _newTitle;
        private string _errorMessage;
        private string _statusMessage;
        private bool _isBusy;
        private bool _hasLoaded;
        private bool _hasLoadedFiles;
        private bool _isShowingFiles;

        public DocumentsViewModel(OtterWorksApiClient api, MainViewModel main)
        {
            _api = api;
            _main = main;

            RefreshCommand = new AsyncRelayCommand(RefreshAsync, () => !IsBusy);
            CreateCommand = new AsyncRelayCommand(CreateDocumentAsync, CanCreate);
            LoadFilesCommand = new AsyncRelayCommand(LoadFilesAsync, () => !IsBusy);
            ShowDocumentsCommand = new AsyncRelayCommand(ShowDocumentsAsync, () => !IsBusy);
            LogoutCommand = new RelayCommand(() => _main.Logout());

            // Initial load; UI shows a busy indicator meanwhile.
            InitialLoad = LoadDocumentsAsync();
        }

        internal Task InitialLoad { get; }

        public ObservableCollection<Document> Documents { get; } = new ObservableCollection<Document>();

        public ObservableCollection<FileItem> Files { get; } = new ObservableCollection<FileItem>();

        public string UserName => _main.CurrentUserName;

        public bool IsEmpty => _hasLoaded && !IsShowingFiles && Documents.Count == 0 && !IsBusy;

        public bool IsFilesEmpty => _hasLoadedFiles && IsShowingFiles && Files.Count == 0 && !IsBusy;

        public bool IsShowingFiles
        {
            get => _isShowingFiles;
            private set
            {
                if (SetProperty(ref _isShowingFiles, value))
                {
                    OnPropertyChanged(nameof(IsShowingDocuments));
                    OnPropertyChanged(nameof(Heading));
                    OnPropertyChanged(nameof(IsEmpty));
                    OnPropertyChanged(nameof(IsFilesEmpty));
                }
            }
        }

        public bool IsShowingDocuments => !IsShowingFiles;

        public string Heading => IsShowingFiles ? "Files" : "Documents";

        public string NewTitle
        {
            get => _newTitle;
            set => SetProperty(ref _newTitle, value);
        }

        public string ErrorMessage
        {
            get => _errorMessage;
            set => SetProperty(ref _errorMessage, value);
        }

        public string StatusMessage
        {
            get => _statusMessage;
            set => SetProperty(ref _statusMessage, value);
        }

        public bool IsBusy
        {
            get => _isBusy;
            set
            {
                if (SetProperty(ref _isBusy, value))
                {
                    OnPropertyChanged(nameof(IsEmpty));
                    OnPropertyChanged(nameof(IsFilesEmpty));
                }
            }
        }

        public ICommand RefreshCommand { get; }

        public ICommand CreateCommand { get; }

        public ICommand LoadFilesCommand { get; }

        public ICommand ShowDocumentsCommand { get; }

        public ICommand LogoutCommand { get; }

        private bool CanCreate() => !IsBusy && !string.IsNullOrWhiteSpace(NewTitle);

        private Task RefreshAsync() => IsShowingFiles ? LoadFilesAsync() : LoadDocumentsAsync();

        internal async Task ShowDocumentsAsync()
        {
            IsShowingFiles = false;
            await LoadDocumentsAsync().ConfigureAwait(true);
        }

        private void HandleApiError(ApiException ex)
        {
            if (ex.StatusCode == HttpStatusCode.Unauthorized)
            {
                if (ReferenceEquals(_main.CurrentViewModel, this))
                {
                    _main.ShowSessionExpired();
                }

                return;
            }

            ErrorMessage = ex.Message;
        }

        private async Task LoadDocumentsAsync()
        {
            ErrorMessage = null;
            IsBusy = true;
            try
            {
                DocumentListResponse result = await _api.GetDocumentsAsync().ConfigureAwait(true);
                Documents.Clear();
                if (result?.Items != null)
                {
                    foreach (Document doc in result.Items)
                    {
                        Documents.Add(doc);
                    }
                }

                StatusMessage = $"{Documents.Count} document(s).";
            }
            catch (ApiException ex)
            {
                HandleApiError(ex);
            }
            finally
            {
                _hasLoaded = true;
                IsBusy = false;
                OnPropertyChanged(nameof(IsEmpty));
            }
        }

        private async Task CreateDocumentAsync()
        {
            ErrorMessage = null;
            IsBusy = true;
            try
            {
                Document created = await _api.CreateDocumentAsync(NewTitle.Trim()).ConfigureAwait(true);
                NewTitle = string.Empty;
                if (created != null)
                {
                    StatusMessage = $"Created \"{created.Title}\".";
                }

                await LoadDocumentsAsync().ConfigureAwait(true);
            }
            catch (ApiException ex)
            {
                HandleApiError(ex);
            }
            finally
            {
                IsBusy = false;
            }
        }

        internal async Task LoadFilesAsync()
        {
            ErrorMessage = null;
            IsBusy = true;
            try
            {
                FileListResponse result = await _api.GetFilesAsync().ConfigureAwait(true);
                Files.Clear();
                if (result?.Files != null)
                {
                    foreach (FileItem file in result.Files)
                    {
                        Files.Add(file);
                    }
                }

                _hasLoadedFiles = true;
                IsShowingFiles = true;
                StatusMessage = $"{Files.Count} file(s).";
            }
            catch (ApiException ex)
            {
                HandleApiError(ex);
            }
            finally
            {
                IsBusy = false;
                OnPropertyChanged(nameof(IsFilesEmpty));
            }
        }
    }
}
