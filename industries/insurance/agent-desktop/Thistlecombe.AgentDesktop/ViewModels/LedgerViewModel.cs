using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using System.Windows.Input;
using OtterWorks.Desktop.Mvvm;
using OtterWorks.Desktop.Services;

namespace Thistlecombe.AgentDesktop.ViewModels
{
    /// <summary>A read-only list screen that loads its rows from one gateway route.</summary>
    public abstract class LedgerViewModel<TRow> : ObservableObject
    {
        private string? _summary;
        private string? _errorMessage;
        private bool _isBusy;

        protected LedgerViewModel()
        {
            RefreshCommand = new AsyncRelayCommand(LoadAsync, () => !IsBusy);
        }

        public ObservableCollection<TRow> Rows { get; } = new ObservableCollection<TRow>();

        public string? Summary
        {
            get => _summary;
            private set => SetProperty(ref _summary, value);
        }

        public string? ErrorMessage
        {
            get => _errorMessage;
            private set => SetProperty(ref _errorMessage, value);
        }

        public bool IsBusy
        {
            get => _isBusy;
            private set => SetProperty(ref _isBusy, value);
        }

        public ICommand RefreshCommand { get; }

        public async Task LoadAsync()
        {
            IsBusy = true;
            ErrorMessage = null;
            try
            {
                IReadOnlyList<TRow> rows = await FetchAsync();
                Rows.Clear();
                foreach (TRow row in rows)
                {
                    Rows.Add(row);
                }

                Summary = Summarize(rows);
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

        protected abstract Task<IReadOnlyList<TRow>> FetchAsync();

        protected abstract string Summarize(IReadOnlyList<TRow> rows);
    }
}
