require 'rails_helper'

RSpec.describe 'Admin API role authorization', type: :request do
  def bearer(payload)
    token = JWT.encode({ sub: SecureRandom.uuid, exp: 1.hour.from_now.to_i }.merge(payload),
                       Rails.application.secrets.jwt_secret, 'HS256')
    { 'Authorization' => "Bearer #{token}" }
  end

  let!(:target) { create(:admin_user) }

  context 'when the caller is authenticated but not an admin' do
    [{ role: 'viewer' }, { role: 'editor' }, { roles: ['USER'] }, {}].each do |claims|
      it "returns 403 for #{claims.inspect} on GET /api/v1/admin/users" do
        get '/api/v1/admin/users', headers: bearer(claims)
        expect(response).to have_http_status(:forbidden)
        expect(JSON.parse(response.body)['error']).to eq('Admin role required')
      end
    end

    it 'cannot suspend a user' do
      put "/api/v1/admin/users/#{target.id}/suspend", params: { reason: 'x' }, headers: bearer(roles: ['USER'])
      expect(response).to have_http_status(:forbidden)
      expect(target.reload.status).to eq('active')
    end

    it 'cannot grant super_admin' do
      put "/api/v1/admin/users/#{target.id}", params: { user: { role: 'super_admin' } },
                                              headers: bearer(roles: ['USER'])
      expect(response).to have_http_status(:forbidden)
      expect(target.reload.role).to eq('viewer')
    end
  end

  context 'when the caller is an admin' do
    [{ role: 'super_admin' }, { role: 'admin' }, { roles: %w[ADMIN USER] }].each do |claims|
      it "allows #{claims.inspect} to list users" do
        get '/api/v1/admin/users', headers: bearer(claims)
        expect(response).to have_http_status(:ok)
        expect(JSON.parse(response.body)['users'].pluck('id')).to include(target.id)
      end
    end

    it 'allows an auth-service ADMIN token to suspend a user' do
      put "/api/v1/admin/users/#{target.id}/suspend", params: { reason: 'x' }, headers: bearer(roles: %w[ADMIN USER])
      expect(response).to have_http_status(:ok)
      expect(target.reload.status).to eq('suspended')
    end
  end

  it 'still requires a token' do
    get '/api/v1/admin/users'
    expect(response).to have_http_status(:unauthorized)
  end

  it 'leaves secret-guarded and health paths outside the role check' do
    get '/health', headers: bearer(roles: ['USER'])
    expect(response).to have_http_status(:ok)
  end
end
