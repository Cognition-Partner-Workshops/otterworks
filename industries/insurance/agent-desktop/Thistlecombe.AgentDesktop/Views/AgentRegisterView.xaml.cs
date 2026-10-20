using System.Windows.Controls;
using OtterWorks.Desktop.ViewModels;

namespace Thistlecombe.AgentDesktop.Views
{
    public partial class AgentRegisterView : UserControl
    {
        public AgentRegisterView()
        {
            InitializeComponent();
        }

        private void PasswordInput_PasswordChanged(object sender, System.Windows.RoutedEventArgs e)
        {
            if (DataContext is RegisterViewModel vm)
            {
                vm.Password = PasswordInput.Password;
            }
        }
    }
}
