require 'rails_helper'

RSpec.describe 'Admin API JWT authentication', type: :request do
  let(:secret) { Rails.application.secrets.jwt_secret }

  def token_for(payload, key = secret)
    JWT.encode(payload, key, 'HS256')
  end

  def bearer(token)
    { 'Authorization' => "Bearer #{token}" }
  end

  it 'leaves /health unauthenticated' do
    get '/health'
    expect(response).to have_http_status(:ok)
  end

  it 'rejects admin requests with no token' do
    get '/api/v1/admin/users'
    expect(response).to have_http_status(:unauthorized)
    expect(JSON.parse(response.body)['error']).to eq('Missing authorization token')
  end

  it 'rejects a non-Bearer authorization header' do
    get '/api/v1/admin/users', headers: { 'Authorization' => 'Basic Zm9vOmJhcg==' }
    expect(response).to have_http_status(:unauthorized)
  end

  it 'rejects a token signed with the wrong secret' do
    get '/api/v1/admin/users', headers: bearer(token_for({ sub: 'u1', exp: 1.hour.from_now.to_i }, 'wrong-secret'))
    expect(response).to have_http_status(:unauthorized)
    expect(JSON.parse(response.body)['error']).to eq('Invalid or expired token')
  end

  it 'rejects an expired token' do
    get '/api/v1/admin/users', headers: bearer(token_for({ sub: 'u1', exp: 1.minute.ago.to_i }))
    expect(response).to have_http_status(:unauthorized)
  end

  it 'rejects a malformed token' do
    get '/api/v1/admin/users', headers: bearer('not-a-jwt')
    expect(response).to have_http_status(:unauthorized)
  end

  it 'accepts a valid super_admin token' do
    create(:admin_user)
    get '/api/v1/admin/users', headers: auth_headers(role: 'super_admin')
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)['users'].length).to eq(1)
  end

  it 'records the JWT subject as the audit actor' do
    user = create(:admin_user)
    actor_id = SecureRandom.uuid
    put "/api/v1/admin/users/#{user.id}/suspend", params: { reason: 'qa' },
                                                  headers: auth_headers(user_id: actor_id, email: 'qa@otterworks.dev')
    expect(response).to have_http_status(:ok)
    log = AuditLog.find_by!(action: 'user.suspended', resource_id: user.id)
    expect(log.actor_id).to eq(actor_id)
    expect(log.actor_email).to eq('qa@otterworks.dev')
  end

  # [REAL] Admin endpoints only check that the JWT is valid; there is no role check, so a
  # regular end-user token can list, suspend and re-role users. Not on the planted-bug list.
  # Left failing on purpose so the gap stays visible.
  %w[viewer USER].each do |role|
    it "forbids a #{role} token from listing admin users [REAL: no role check]" do
      get '/api/v1/admin/users', headers: auth_headers(role: role)
      expect(response).to have_http_status(:forbidden)
    end
  end

  it 'forbids a token with no role claim from changing user roles [REAL: no role check]' do
    user = create(:admin_user)
    put "/api/v1/admin/users/#{user.id}", params: { user: { role: 'super_admin' } },
                                          headers: bearer(token_for({ sub: 'u1', exp: 1.hour.from_now.to_i }))
    expect(response).to have_http_status(:forbidden)
    expect(user.reload.role).to eq('viewer')
  end
end
