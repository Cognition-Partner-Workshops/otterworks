using System.Windows.Controls;
using OtterWorks.Desktop.ViewModels;

namespace Thistlecombe.AgentDesktop.Views
{
    public partial class AgentLoginView : UserControl
    {
        public AgentLoginView()
        {
            InitializeComponent();
        }

        private void PasswordInput_PasswordChanged(object sender, System.Windows.RoutedEventArgs e)
        {
            if (DataContext is LoginViewModel vm)
            {
                vm.Password = PasswordInput.Password;
            }
        }
    }
}
