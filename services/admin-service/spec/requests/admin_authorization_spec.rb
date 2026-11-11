require 'rails_helper'

RSpec.describe 'Admin authorization', type: :request do
  def headers_for(claims = {})
    payload = { 'sub' => SecureRandom.uuid, 'exp' => 1.hour.from_now.to_i }.merge(claims)
    token = JWT.encode(payload, Rails.application.secrets.jwt_secret, 'HS256')
    { 'Authorization' => "Bearer #{token}" }
  end

  let!(:user) { create(:admin_user) }

  it 'forbids viewers and editors from accessing the finance dashboard' do
    %w[viewer editor].each do |role|
      get '/api/v1/admin/finance/dashboard', headers: headers_for('role' => role)
      expect(response).to have_http_status(:forbidden)
    end
  end

  it 'allows viewers to read records' do
    get "/api/v1/admin/users/#{user.id}", headers: headers_for('role' => 'viewer')
    expect(response).to have_http_status(:ok)
  end

  it 'forbids viewer mutations before looking up a record' do
    expect(AdminAuthorization).not_to receive(:scope)
    put "/api/v1/admin/users/#{user.id}/suspend", headers: headers_for('role' => 'viewer')
    expect(response).to have_http_status(:forbidden)
    expect(user.reload.status).to eq('active')
  end

  it 'forbids tokens with missing or unknown roles' do
    [{}, { 'roles' => ['USER'] }].each do |claims|
      get '/api/v1/admin/users', headers: headers_for(claims)
      expect(response).to have_http_status(:forbidden)
    end
  end

  it 'accepts auth-service roles arrays and selects the highest privilege across claims' do
    put "/api/v1/admin/users/#{user.id}", params: { user: { display_name: 'Updated' } },
        headers: headers_for('role' => 'viewer', 'roles' => %w[EDITOR ADMIN])
    expect(response).to have_http_status(:ok)
    expect(user.reload.display_name).to eq('Updated')
  end

  it 'lets editors create content but not mutate users' do
    post '/api/v1/admin/announcements', params: { announcement: { title: 'Notice', body: 'Content' } },
         headers: headers_for('role' => 'editor')
    expect(response).to have_http_status(:created)

    put "/api/v1/admin/users/#{user.id}", params: { user: { display_name: 'Denied' } },
        headers: headers_for('role' => 'editor')
    expect(response).to have_http_status(:forbidden)
    expect(user.reload.display_name).not_to eq('Denied')
  end

  it 'forbids admins from changing roles, including their own' do
    put "/api/v1/admin/users/#{user.id}", params: { user: { role: 'super_admin' } },
        headers: headers_for('role' => 'admin', 'sub' => user.id)
    expect(response).to have_http_status(:forbidden)
    expect(user.reload.role).to eq('viewer')
  end

  it 'forbids admins from accessing configuration' do
    get '/api/v1/admin/config', headers: headers_for('role' => 'admin')
    expect(response).to have_http_status(:forbidden)
  end

  it 'allows super admins to assign a valid role but rejects unknown roles' do
    put "/api/v1/admin/users/#{user.id}", params: { user: { role: 'editor' } },
        headers: headers_for('roles' => %w[ADMIN SUPER_ADMIN])
    expect(response).to have_http_status(:ok)
    expect(user.reload.role).to eq('editor')

    put "/api/v1/admin/users/#{user.id}", params: { user: { role: 'owner' } },
        headers: headers_for('role' => 'super_admin')
    expect(response).to have_http_status(:unprocessable_entity)
    expect(user.reload.role).to eq('editor')
  end

  it 'forbids admin bulk role operations even when no role is supplied' do
    post '/api/v1/admin/bulk/users', params: { operation: 'update_role', user_ids: [user.id] },
         headers: headers_for('role' => 'admin')
    expect(response).to have_http_status(:forbidden)
    expect(user.reload.role).to eq('viewer')
  end

  it 'forbids smuggling a role into other bulk operations' do
    post '/api/v1/admin/bulk/users', params: { operation: 'activate', user_ids: [user.id], role: 'super_admin' },
         headers: headers_for('role' => 'admin')
    expect(response).to have_http_status(:forbidden)
    expect(user.reload.role).to eq('viewer')
  end

  it 'allows ordinary admin bulk operations' do
    post '/api/v1/admin/bulk/users', params: { operation: 'suspend', user_ids: [user.id] },
         headers: headers_for('role' => 'admin')
    expect(response).to have_http_status(:ok)
    expect(user.reload.status).to eq('suspended')
  end

  it 'validates super admin bulk role assignments before changing any records' do
    [nil, 'owner'].each do |role|
      post '/api/v1/admin/bulk/users', params: { operation: 'update_role', user_ids: [user.id], role: role },
           headers: headers_for('role' => 'super_admin')
      expect(response).to have_http_status(:unprocessable_entity)
      expect(user.reload.role).to eq('viewer')
    end

    post '/api/v1/admin/bulk/users', params: { operation: 'update_role', user_ids: [user.id], role: 'admin' },
         headers: headers_for('role' => 'super_admin')
    expect(response).to have_http_status(:ok)
    expect(user.reload.role).to eq('admin')
  end

  it 'preserves unauthenticated health checks' do
    get '/health'
    expect(response).to have_http_status(:ok)
  end
end
