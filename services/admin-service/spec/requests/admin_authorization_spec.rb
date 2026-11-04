require 'rails_helper'

RSpec.describe 'Admin API authorization' do
  let(:json_headers) { { 'Content-Type' => 'application/json' } }

  admin_routes = [
    [:get, '/api/v1/admin/users'],
    [:get, '/api/v1/admin/health/services'],
    [:get, '/api/v1/admin/features'],
    [:post, '/api/v1/admin/features'],
    [:get, '/api/v1/admin/config'],
    [:get, '/api/v1/admin/audit-logs'],
    [:get, '/api/v1/admin/quotas/00000000-0000-0000-0000-000000000000'],
    [:get, '/api/v1/admin/metrics/summary'],
    [:get, '/api/v1/admin/announcements'],
    [:get, '/api/v1/admin/incidents'],
    [:post, '/api/v1/admin/incidents'],
    [:post, '/api/v1/admin/bulk/users'],
    [:get, '/api/v1/admin/settings/auto_investigate'],
    [:put, '/api/v1/admin/settings/auto_investigate']
  ]

  describe 'self-signup USER token' do
    let(:headers) { auth_headers(roles: %w[USER]).merge(json_headers) }

    admin_routes.each do |verb, path|
      it "is forbidden on #{verb.upcase} #{path}" do
        public_send(verb, path, headers: headers, params: {}.to_json)
        expect(response).to have_http_status(:forbidden)
      end
    end

    it 'cannot promote itself or demote another user' do
      victim = create(:admin_user, :super_admin)
      put "/api/v1/admin/users/#{victim.id}", headers: headers, params: { user: { role: 'viewer' } }.to_json
      expect(response).to have_http_status(:forbidden)
      expect(victim.reload.role).to eq('super_admin')
    end
  end

  it 'forbids EDITOR tokens' do
    get '/api/v1/admin/users', headers: auth_headers(roles: %w[USER EDITOR])
    expect(response).to have_http_status(:forbidden)
  end

  it 'forbids tokens that carry only the legacy singular role claim' do
    token = JWT.encode({ sub: SecureRandom.uuid, role: 'super_admin', exp: 1.hour.from_now.to_i },
                       Rails.application.secrets.jwt_secret, 'HS256')
    get '/api/v1/admin/users', headers: { 'Authorization' => "Bearer #{token}" }
    expect(response).to have_http_status(:forbidden)
  end

  it 'still rejects requests without a token' do
    get '/api/v1/admin/users'
    expect(response).to have_http_status(:unauthorized)
  end

  it 'allows ADMIN tokens to use the admin API' do
    create(:admin_user)
    get '/api/v1/admin/users', headers: auth_headers(roles: %w[USER ADMIN])
    expect(response).to have_http_status(:ok)
  end

  it 'keeps /health and /metrics open' do
    get '/health'
    expect(response).to have_http_status(:ok)
    get '/metrics'
    expect(response).to have_http_status(:ok)
  end

  it 'keeps the alert ingest webhook behind its shared secret, not the admin role' do
    post '/api/v1/admin/alerts/ingest', headers: json_headers, params: { alerts: [] }.to_json
    expect(response).not_to have_http_status(:forbidden)
  end

  describe 'role changes through the gateway token' do
    let(:target) { create(:admin_user, :editor) }

    it 'denies ADMIN tokens' do
      put "/api/v1/admin/users/#{target.id}",
          headers: auth_headers(roles: %w[USER ADMIN]).merge(json_headers),
          params: { user: { role: 'super_admin' } }.to_json
      expect(response).to have_http_status(:forbidden)
      expect(target.reload.role).to eq('editor')
    end

    it 'allows OWNER tokens' do
      put "/api/v1/admin/users/#{target.id}",
          headers: auth_headers(roles: %w[USER OWNER]).merge(json_headers),
          params: { user: { role: 'admin' } }.to_json
      expect(response).to have_http_status(:ok)
      expect(target.reload.role).to eq('admin')
    end
  end
end
