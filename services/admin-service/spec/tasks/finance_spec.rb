require 'rails_helper'
require 'rake'

RSpec.describe 'finance:refresh_dashboard' do
  before(:all) { Rails.application.load_tasks }

  let(:task) { Rake::Task['finance:refresh_dashboard'] }
  let(:queries) { instance_double(FinanceWarehouse::DashboardQueries) }

  before do
    task.reenable
    allow(FinanceWarehouse::DashboardQueries).to receive(:new).and_return(queries)
  end

  it 'prints the refreshed dashboard as JSON' do
    allow(queries).to receive(:refresh).and_return({ ar_open_balance: '45000.0' })
    expect { task.invoke }.to output("{\"ar_open_balance\":\"45000.0\"}\n").to_stdout
    expect(queries).to have_received(:refresh)
  end

  it 'fails when the warehouse is disabled' do
    allow(queries).to receive(:refresh).and_raise(FinanceWarehouse::DashboardQueries::Disabled)
    expect { task.invoke }.to raise_error(FinanceWarehouse::DashboardQueries::Disabled)
  end
end
