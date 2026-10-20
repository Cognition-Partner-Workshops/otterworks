using System.Windows;
using OtterWorks.Desktop.Services;
using OtterWorks.Desktop.ViewModels;
using Thistlecombe.AgentDesktop.Services;
using Thistlecombe.AgentDesktop.ViewModels;
using Thistlecombe.AgentDesktop.Views;

namespace Thistlecombe.AgentDesktop
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            AppSettings settings = AppSettings.Load();
            var session = new SessionState(settings.PersistTokens);
            session.TryRestore();

            var main = new MainViewModel(new OtterWorksApiClient(settings, session), session);
            var shell = new AgentShellViewModel(main, new InsuranceApiClient(settings, session));

            new AgentShellWindow { DataContext = shell }.Show();
        }
    }
}
