require 'rails_helper'

RSpec.describe 'Admin API authorization', type: :request do
  let(:target) { create(:admin_user) }

  def token_headers(claims)
    payload = { sub: SecureRandom.uuid, email: 'caller@otterworks.com',
                exp: 1.hour.from_now.to_i, iat: Time.current.to_i }.merge(claims)
    { 'Authorization' => "Bearer #{JWT.encode(payload, Rails.application.secrets.jwt_secret, 'HS256')}" }
  end

  context 'with a token whose roles are only USER' do
    let(:headers) { token_headers(roles: ['USER']) }

    it 'returns 403 on GET /api/v1/admin/users' do
      get '/api/v1/admin/users', headers: headers
      expect(response).to have_http_status(:forbidden)
    end

    it 'returns 403 on PUT /api/v1/admin/users/:id and leaves the user unchanged' do
      put "/api/v1/admin/users/#{target.id}", params: { user: { role: 'super_admin' } }, headers: headers
      expect(response).to have_http_status(:forbidden)
      expect(target.reload.role).not_to eq('super_admin')
    end

    it 'returns 403 on PUT /api/v1/admin/users/:id/suspend' do
      put "/api/v1/admin/users/#{target.id}/suspend", headers: headers
      expect(response).to have_http_status(:forbidden)
      expect(target.reload.status).not_to eq('suspended')
    end

    it 'returns 403 on POST /api/v1/admin/bulk/users' do
      post '/api/v1/admin/bulk/users',
           params: { operation: 'suspend', user_ids: [target.id] }, headers: headers
      expect(response).to have_http_status(:forbidden)
    end
  end

  it 'returns 403 when the token has no roles claim' do
    get '/api/v1/admin/users', headers: token_headers({})
    expect(response).to have_http_status(:forbidden)
  end

  it 'ignores a self-declared legacy role claim' do
    get '/api/v1/admin/users', headers: token_headers(role: 'super_admin', roles: ['USER'])
    expect(response).to have_http_status(:forbidden)
  end

  it 'returns 403 when roles is a string rather than a list' do
    get '/api/v1/admin/users', headers: token_headers(roles: 'NOT_ADMIN_USER')
    expect(response).to have_http_status(:forbidden)
  end

  context 'with a token whose roles include ADMIN' do
    let(:headers) { token_headers(roles: %w[ADMIN USER]) }

    it 'returns 200 on GET /api/v1/admin/users' do
      get '/api/v1/admin/users', headers: headers
      expect(response).to have_http_status(:ok)
    end

    it 'returns 200 on PUT /api/v1/admin/users/:id' do
      put "/api/v1/admin/users/#{target.id}", params: { user: { display_name: 'Renamed' } }, headers: headers
      expect(response).to have_http_status(:ok)
    end
  end

  it 'still returns 401 without a token' do
    get '/api/v1/admin/users'
    expect(response).to have_http_status(:unauthorized)
  end

  it 'leaves the alert webhook to its own secret check' do
    post '/api/v1/admin/alerts/ingest', params: { alerts: [] }, as: :json
    expect(response).not_to have_http_status(:forbidden)
  end

  it 'leaves /health open' do
    get '/health'
    expect(response).not_to have_http_status(:forbidden)
  end
end
