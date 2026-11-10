namespace :finance do
  desc 'Refresh the finance dashboard cache'
  task refresh_dashboard: :environment do
    puts FinanceWarehouse::DashboardQueries.new.refresh.to_json
  end
end
