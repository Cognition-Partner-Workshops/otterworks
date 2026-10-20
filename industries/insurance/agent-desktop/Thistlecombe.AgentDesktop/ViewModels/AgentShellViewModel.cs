using System.ComponentModel;
using System.Windows.Input;
using OtterWorks.Desktop.Mvvm;
using OtterWorks.Desktop.ViewModels;
using Thistlecombe.AgentDesktop.Services;

namespace Thistlecombe.AgentDesktop.ViewModels
{
    public enum AgentSection
    {
        Policies,
        Claims,
        Documents,
    }

    /// <summary>
    /// Wraps the shared <see cref="MainViewModel"/>: sign-in and registration stay its job; once signed in
    /// the agent moves between Policies, Claims and the shared Documents screen.
    /// </summary>
    public class AgentShellViewModel : ObservableObject
    {
        private readonly MainViewModel _main;
        private readonly InsuranceApiClient _insurance;
        private AgentSection _section = AgentSection.Policies;
        private bool _wasAuthenticated;
        private PoliciesViewModel? _policies;
        private ClaimsViewModel? _claims;

        public AgentShellViewModel(MainViewModel main, InsuranceApiClient insurance)
        {
            _main = main;
            _insurance = insurance;
            _wasAuthenticated = main.IsAuthenticated;
            SignOutCommand = new RelayCommand(() => _main.Logout());
            _main.PropertyChanged += OnMainChanged;
        }

        public bool IsAuthenticated => _main.IsAuthenticated;

        public string? CurrentUserName => _main.CurrentUserName;

        public ICommand SignOutCommand { get; }

        public AgentSection Section
        {
            get => _section;
            set
            {
                if (SetProperty(ref _section, value))
                {
                    RaiseNavigation();
                }
            }
        }

        public bool IsPoliciesSection
        {
            get => Section == AgentSection.Policies;
            set { if (value) Section = AgentSection.Policies; }
        }

        public bool IsClaimsSection
        {
            get => Section == AgentSection.Claims;
            set { if (value) Section = AgentSection.Claims; }
        }

        public bool IsDocumentsSection
        {
            get => Section == AgentSection.Documents;
            set { if (value) Section = AgentSection.Documents; }
        }

        public object? CurrentContent
        {
            get
            {
                if (!_main.IsAuthenticated)
                {
                    return _main.CurrentViewModel;
                }

                switch (Section)
                {
                    case AgentSection.Policies:
                        return _policies ??= new PoliciesViewModel(_insurance);
                    case AgentSection.Claims:
                        return _claims ??= new ClaimsViewModel(_insurance);
                    default:
                        return _main.CurrentViewModel;
                }
            }
        }

        private void OnMainChanged(object? sender, PropertyChangedEventArgs e)
        {
            bool now = _main.IsAuthenticated;
            if (now != _wasAuthenticated)
            {
                _policies = null;
                _claims = null;
                _section = AgentSection.Policies;
                _wasAuthenticated = now;
            }

            OnPropertyChanged(nameof(IsAuthenticated));
            OnPropertyChanged(nameof(CurrentUserName));
            RaiseNavigation();
        }

        private void RaiseNavigation()
        {
            OnPropertyChanged(nameof(Section));
            OnPropertyChanged(nameof(IsPoliciesSection));
            OnPropertyChanged(nameof(IsClaimsSection));
            OnPropertyChanged(nameof(IsDocumentsSection));
            OnPropertyChanged(nameof(CurrentContent));
        }
    }
}
