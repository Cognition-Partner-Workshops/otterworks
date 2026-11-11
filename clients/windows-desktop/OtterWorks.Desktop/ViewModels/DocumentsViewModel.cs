using System.Collections.ObjectModel;
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
        private bool _loadFailed;
        private bool _isShowingFiles;

        public DocumentsViewModel(OtterWorksApiClient api, MainViewModel main)
        {
            _api = api;
            _main = main;

            RefreshCommand = new AsyncRelayCommand(RefreshAsync, () => !IsBusy);
            CreateCommand = new AsyncRelayCommand(CreateDocumentAsync, CanCreate);
            LoadFilesCommand = new AsyncRelayCommand(LoadFilesAsync, () => !IsBusy);
            ShowDocumentsCommand = new AsyncRelayCommand(LoadDocumentsAsync, () => !IsBusy);
            LogoutCommand = new RelayCommand(() => _main.Logout());

            // Fire-and-forget initial load; UI shows a busy indicator meanwhile.
            InitialLoad = LoadDocumentsAsync();
        }

        public ObservableCollection<Document> Documents { get; } = new ObservableCollection<Document>();

        public ObservableCollection<FileItem> Files { get; } = new ObservableCollection<FileItem>();

        public string UserName => _main.CurrentUserName;

        public string Heading => IsShowingFiles ? "Files" : "Documents";

        public bool IsShowingFiles
        {
            get => _isShowingFiles;
            private set
            {
                if (SetProperty(ref _isShowingFiles, value))
                {
                    OnPropertyChanged(nameof(IsShowingDocuments));
                    OnPropertyChanged(nameof(Heading));
                    RaiseStateChanged();
                }
            }
        }

        public bool IsShowingDocuments => !IsShowingFiles;

        public bool IsEmpty => IsShowingDocuments && _hasLoaded && !_loadFailed && Documents.Count == 0 && !IsBusy;

        public bool IsFilesEmpty => IsShowingFiles && _hasLoadedFiles && !_loadFailed && Files.Count == 0 && !IsBusy;

        public bool IsLoadFailed => _loadFailed && !IsBusy;

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
                    RaiseStateChanged();
                }
            }
        }

        public ICommand RefreshCommand { get; }

        public ICommand CreateCommand { get; }

        public ICommand LoadFilesCommand { get; }

        public ICommand ShowDocumentsCommand { get; }

        public ICommand LogoutCommand { get; }

        internal Task InitialLoad { get; }

        private bool CanCreate() => !IsBusy && !string.IsNullOrWhiteSpace(NewTitle);

        private Task RefreshAsync() => IsShowingFiles ? LoadFilesAsync() : LoadDocumentsAsync();

        internal async Task LoadDocumentsAsync()
        {
            ErrorMessage = null;
            IsShowingFiles = false;
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

                _loadFailed = false;
                StatusMessage = $"{Documents.Count} document(s).";
            }
            catch (ApiException ex)
            {
                Documents.Clear();
                _loadFailed = true;
                StatusMessage = null;
                ErrorMessage = ex.Message;
            }
            finally
            {
                _hasLoaded = true;
                IsBusy = false;
                RaiseStateChanged();
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
                ErrorMessage = ex.Message;
            }
            finally
            {
                IsBusy = false;
            }
        }

        internal async Task LoadFilesAsync()
        {
            ErrorMessage = null;
            IsShowingFiles = true;
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

                _loadFailed = false;
                StatusMessage = $"{Files.Count} file(s).";
            }
            catch (ApiException ex)
            {
                Files.Clear();
                _loadFailed = true;
                StatusMessage = null;
                ErrorMessage = ex.Message;
            }
            finally
            {
                _hasLoadedFiles = true;
                IsBusy = false;
                RaiseStateChanged();
            }
        }

        private void RaiseStateChanged()
        {
            OnPropertyChanged(nameof(IsEmpty));
            OnPropertyChanged(nameof(IsFilesEmpty));
            OnPropertyChanged(nameof(IsLoadFailed));
        }
    }
}
