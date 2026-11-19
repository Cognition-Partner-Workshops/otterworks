require 'rails_helper'

RSpec.describe Api::V1::Admin::HealthController do
  it 'returns dependency health details for the admin dashboard' do
    set_jwt_env(request)
    allow(HealthChecker).to receive(:check_all).and_return(status: 'degraded', services: [{ name: 'search-service', status: 'unhealthy' }])
    get :services
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)).to eq('status' => 'degraded', 'services' => [{ 'name' => 'search-service', 'status' => 'unhealthy' }])
  end
end
