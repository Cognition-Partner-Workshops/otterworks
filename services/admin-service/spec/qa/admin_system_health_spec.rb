require 'rails_helper'

RSpec.describe HealthChecker do
  def http_double(code)
    instance_double(Net::HTTP, :open_timeout= => nil, :read_timeout= => nil,
                               get: instance_double(Net::HTTPResponse, code: code))
  end

  before do
    allow(described_class).to receive_messages(check_database: { status: 'healthy' }, check_redis: { status: 'healthy' })
  end

  it 'reports healthy when every service returns 200' do
    allow(Net::HTTP).to receive(:new).and_return(http_double('200'))
    result = described_class.check_all
    expect(result[:status]).to eq('healthy')
    expect(result[:services].map { |s| s[:name] }).to match_array(described_class::SERVICES)
  end

  it 'reports degraded when one service is unhealthy' do
    allow(Net::HTTP).to receive(:new) do |host, _port|
      host == 'search-service' ? http_double('503') : http_double('200')
    end
    result = described_class.check_all
    expect(result[:status]).to eq('degraded')
    expect(result[:services].find { |s| s[:name] == 'search-service' }[:status]).to eq('unhealthy')
  end

  it 'marks a service unhealthy with the error message when unreachable' do
    allow(Net::HTTP).to receive(:new).and_raise(Errno::ECONNREFUSED)
    status = described_class.check_service('auth-service')
    expect(status.status).to eq('unhealthy')
    expect(status.message).to include('Connection refused')
  end

  it 'honours <SERVICE>_HOST / _PORT overrides' do
    allow(ENV).to receive(:fetch).and_call_original
    allow(ENV).to receive(:fetch).with('AUTH_SERVICE_HOST', 'auth-service').and_return('auth.internal')
    allow(ENV).to receive(:fetch).with('AUTH_SERVICE_PORT', '8081').and_return('9999')
    allow(Net::HTTP).to receive(:new).with('auth.internal', 9999).and_return(http_double('200'))
    expect(described_class.check_service('auth-service').status).to eq('healthy')
  end
end

RSpec.describe Api::V1::Admin::HealthController, type: :controller do
  before { set_jwt_env(request) }

  it 'renders the HealthChecker result' do
    allow(HealthChecker).to receive(:check_all).and_return({ status: 'degraded', services: [] })
    get :services
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)['status']).to eq('degraded')
  end
end

RSpec.describe Api::V1::Admin::MetricsController, type: :controller do
  before { set_jwt_env(request) }

  it 'summarises users, storage and features' do
    create(:admin_user)
    create(:admin_user, :suspended)
    create(:storage_quota, :over_quota)
    create(:feature_flag, :enabled)
    get :summary
    body = JSON.parse(response.body)
    expect(body['users']).to include('total' => 2, 'active' => 1, 'suspended' => 1)
    expect(body['storage']['users_over_quota']).to eq(1)
    expect(body['features']).to include('total' => 1, 'enabled' => 1)
  end
end

RSpec.describe Api::V1::Admin::SettingsController, type: :controller do
  before { set_jwt_env(request) }

  it 'returns the auto-investigate flag' do
    allow(AdminSettingsService).to receive(:auto_investigate_enabled?).and_return(false)
    get :auto_investigate
    expect(JSON.parse(response.body)).to eq('enabled' => false)
  end

  it 'updates the auto-investigate flag' do
    allow(AdminSettingsService).to receive(:set_auto_investigate)
    allow(AdminSettingsService).to receive(:auto_investigate_enabled?).and_return(true)
    put :update_auto_investigate, params: { enabled: 'true' }
    expect(AdminSettingsService).to have_received(:set_auto_investigate).with(true)
    expect(response).to have_http_status(:ok)
  end

  it 'returns 400 when enabled is missing' do
    put :update_auto_investigate
    expect(response).to have_http_status(:bad_request)
  end
end

RSpec.describe 'production environment boot' do
  it 'boots with RAILS_ENV=production' do
    pending '[PLANTED] config/environments/production.rb calls ActiveSupport::TaggedLogging.logger ' \
            '(invalid on Rails 7.1) - AGENTS.md golden-app lab bug'
    output = IO.popen({ 'RAILS_ENV' => 'production', 'SECRET_KEY_BASE' => 'qa', 'JWT_SECRET' => 'qa' },
                      ['bundle', 'exec', 'rails', 'runner', 'puts :booted'],
                      chdir: Rails.root.to_s, err: %i[child out], &:read)
    expect(output).to include('booted')
  end
end
