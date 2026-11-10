require 'rails_helper'

RSpec.describe 'Finance dashboard', type: :request do
  let(:path) { '/api/v1/admin/finance/dashboard' }
  let(:client) { instance_double(FinanceWarehouse::TeradataClient) }

  before do
    allow(FinanceWarehouse::TeradataClient).to receive(:new).and_return(client)
    allow(FinanceWarehouse::DashboardQueries).to receive(:enabled?).and_return(true)
    allow(client).to receive(:query).with(FinanceWarehouse::DashboardQueries::SUMMARY_SQL).and_return([
      { 'DSO' => '27.00', 'AR_OPEN_BALANCE' => '45000.00', 'COLLECTIONS_30_DAYS' => '32000.00' }
    ])
    allow(client).to receive(:query).with(FinanceWarehouse::DashboardQueries::OVERDUE_SQL).and_return([])
  end

  it 'requires a JWT' do
    get path
    expect(response).to have_http_status(:unauthorized)
    expect(client).not_to have_received(:query)
  end

  it 'returns dashboard JSON with the existing JWT helper' do
    get path, headers: auth_headers
    expect(response).to have_http_status(:ok)
    expect(response.parsed_body).to include(
      'dso' => '27.0', 'ar_open_balance' => '45000.0', 'collections_30_days' => '32000.0',
      'top_overdue_accounts' => []
    )
  end

  it 'returns 404 when disabled' do
    allow(FinanceWarehouse::DashboardQueries).to receive(:enabled?).and_return(false)
    get path, headers: auth_headers
    expect(response).to have_http_status(:not_found)
    expect(client).not_to have_received(:query)
  end

  it 'returns a sanitized 503 for warehouse failures' do
    allow(client).to receive(:query).and_raise(FinanceWarehouse::TeradataClient::Unavailable)
    get path, headers: auth_headers
    expect(response).to have_http_status(:service_unavailable)
    expect(response.parsed_body).to eq('error' => 'finance warehouse unavailable')
  end
end
