require 'rails_helper'

# Goes through the full Rack stack (JwtAuthenticator + ApplicationController) with
# tokens shaped like the ones auth-service issues: a `roles` array, no `role` claim.
RSpec.describe 'Admin API role enforcement', type: :request do
  let(:json) { { 'CONTENT_TYPE' => 'application/json', 'ACCEPT' => 'application/json' } }
  let!(:target) { create(:admin_user, role: 'viewer') }

  shared_examples 'rejects the caller with 403' do |method, path_proc, body = nil|
    it "returns 403 for #{method.upcase} #{path_proc.call('<id>')}" do
      send(method, path_proc.call(target.id), params: body&.to_json, headers: headers.merge(json))
      expect(response).to have_http_status(:forbidden)
      expect(response.parsed_body).to eq('error' => 'Admin role required')
    end
  end

  context 'with a self-registered USER token' do
    let(:headers) { auth_headers(email: 'mallory@example.test', roles: %w[USER]) }

    include_examples 'rejects the caller with 403', :get, ->(_) { '/api/v1/admin/users' }
    include_examples 'rejects the caller with 403', :get, ->(id) { "/api/v1/admin/users/#{id}" }
    include_examples 'rejects the caller with 403', :put, ->(id) { "/api/v1/admin/users/#{id}" },
                     { user: { role: 'super_admin' } }
    include_examples 'rejects the caller with 403', :delete, ->(id) { "/api/v1/admin/users/#{id}" }
    include_examples 'rejects the caller with 403', :get, ->(_) { '/api/v1/admin/features' }
    include_examples 'rejects the caller with 403', :get, ->(_) { '/api/v1/admin/config' }
    include_examples 'rejects the caller with 403', :get, ->(_) { '/api/v1/admin/audit-logs' }
    include_examples 'rejects the caller with 403', :get, ->(_) { '/api/v1/admin/health/services' }
    include_examples 'rejects the caller with 403', :get, ->(_) { '/api/v1/admin/settings/auto_investigate' }
    include_examples 'rejects the caller with 403', :post, ->(_) { '/api/v1/admin/bulk/users' },
                     { operation: 'update_role', role: 'super_admin', user_ids: ['<id>'] }

    it 'does not change the target role through a bulk update_role' do
      post '/api/v1/admin/bulk/users',
           params: { operation: 'update_role', role: 'super_admin', user_ids: [target.id] }.to_json,
           headers: headers.merge(json)
      expect(response).to have_http_status(:forbidden)
      expect(target.reload.role).to eq('viewer')
    end
  end

  context 'with a token carrying the legacy `role` claim but no ADMIN in `roles`' do
    it 'returns 403' do
      payload = { sub: SecureRandom.uuid, email: 'legacy@example.test', role: 'super_admin',
                  exp: 1.hour.from_now.to_i, iat: Time.current.to_i }
      token = JWT.encode(payload, Rails.application.secrets.jwt_secret, 'HS256')
      get '/api/v1/admin/users', headers: { 'Authorization' => "Bearer #{token}" }
      expect(response).to have_http_status(:forbidden)
    end
  end

  context 'with an ADMIN token' do
    let(:headers) { auth_headers(roles: %w[ADMIN USER]) }

    it 'lists users' do
      get '/api/v1/admin/users', headers: headers
      expect(response).to have_http_status(:ok)
      expect(response.parsed_body['total']).to eq(1)
    end

    it 'runs a bulk update_role' do
      post '/api/v1/admin/bulk/users',
           params: { operation: 'update_role', role: 'admin', user_ids: [target.id] }.to_json,
           headers: headers.merge(json)
      expect(response).to have_http_status(:ok)
      expect(target.reload.role).to eq('admin')
    end
  end

  context 'without a token' do
    it 'returns 401 from the authenticator' do
      get '/api/v1/admin/users'
      expect(response).to have_http_status(:unauthorized)
    end
  end

  context 'with routes that carry their own secret check' do
    it 'serves /health without a token' do
      get '/health'
      expect(response).to have_http_status(:ok)
    end

    it 'still accepts the alert webhook without an admin token' do
      post '/api/v1/admin/alerts/ingest', params: { alerts: [] }.to_json, headers: json
      expect(response).to have_http_status(:ok)
    end

    it 'still lets the chaos endpoint answer without an admin token' do
      post '/api/v1/admin/chaos', params: { service: 'nope', scenario: 'nope' }.to_json, headers: json
      expect(response).to have_http_status(:unprocessable_entity)
    end
  end
end
