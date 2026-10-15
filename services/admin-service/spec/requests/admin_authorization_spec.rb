require 'rails_helper'

RSpec.describe 'Admin API authorization' do
  # auth-service issues `roles` as a list; self-registered users get ["USER"].
  let(:user_headers) { auth_headers(role: nil, roles: ['USER']) }
  let(:admin_headers) { auth_headers(role: nil, roles: %w[ADMIN USER]) }
  let(:super_admin_headers) { auth_headers(role: 'super_admin') }
  let(:id) { SecureRandom.uuid }

  admin_routes = [
    [:get, '/api/v1/admin/users'],
    [:get, '/api/v1/admin/users/:id'],
    [:put, '/api/v1/admin/users/:id', { user: { role: 'super_admin' } }],
    [:put, '/api/v1/admin/users/:id/role', { role: 'super_admin' }],
    [:delete, '/api/v1/admin/users/:id'],
    [:put, '/api/v1/admin/users/:id/suspend'],
    [:put, '/api/v1/admin/users/:id/activate'],
    [:get, '/api/v1/admin/health/services'],
    [:get, '/api/v1/admin/features'],
    [:post, '/api/v1/admin/features', { feature_flag: { name: 'x' } }],
    [:put, '/api/v1/admin/features/:id', { feature_flag: { enabled: true } }],
    [:delete, '/api/v1/admin/features/:id'],
    [:get, '/api/v1/admin/config'],
    [:put, '/api/v1/admin/config/:id', { config: { value: 'x' } }],
    [:get, '/api/v1/admin/audit-logs'],
    [:get, '/api/v1/admin/quotas/:id'],
    [:put, '/api/v1/admin/quotas/:id', { quota: { quota_bytes: 1 } }],
    [:get, '/api/v1/admin/metrics/summary'],
    [:get, '/api/v1/admin/announcements'],
    [:post, '/api/v1/admin/announcements', { announcement: { title: 'x' } }],
    [:get, '/api/v1/admin/incidents'],
    [:post, '/api/v1/admin/incidents', { incident: { title: 'x', description: 'y', severity: 'high' } }],
    [:put, '/api/v1/admin/incidents/:id', { incident: { status: 'resolved' } }],
    [:delete, '/api/v1/admin/incidents/:id'],
    [:post, '/api/v1/admin/incidents/:id/trigger_session'],
    [:post, '/api/v1/admin/bulk/users', { operation: 'delete', user_ids: ['x'] }],
    [:get, '/api/v1/admin/settings/auto_investigate'],
    [:put, '/api/v1/admin/settings/auto_investigate', { enabled: true }]
  ]

  describe 'non-admin callers' do
    admin_routes.each do |verb, path, body|
      it "rejects a USER token on #{verb.upcase} #{path} with 403" do
        public_send(verb, path.sub(':id', id), params: body, headers: user_headers, as: :json)
        expect(response).to have_http_status(:forbidden)
        expect(response.parsed_body).to eq('error' => 'Forbidden')
      end
    end

    %w[viewer editor].each do |role|
      it "rejects a #{role} role claim" do
        get '/api/v1/admin/users', headers: auth_headers(role: role)
        expect(response).to have_http_status(:forbidden)
      end
    end

    it 'rejects a token with no role claim at all' do
      get '/api/v1/admin/users', headers: auth_headers(role: nil)
      expect(response).to have_http_status(:forbidden)
    end

    it 'still returns 401 when no token is sent' do
      get '/api/v1/admin/users'
      expect(response).to have_http_status(:unauthorized)
    end

    it 'cannot escalate a user to super_admin' do
      target = create(:admin_user, role: 'viewer')
      put "/api/v1/admin/users/#{target.id}", params: { user: { role: 'super_admin' } },
                                              headers: user_headers, as: :json
      put "/api/v1/admin/users/#{target.id}/role", params: { role: 'super_admin' }, headers: user_headers, as: :json
      post '/api/v1/admin/bulk/users', params: { operation: 'update_role', user_ids: [target.id], role: 'super_admin' },
                                       headers: user_headers, as: :json
      expect(target.reload.role).to eq('viewer')
    end

    it 'cannot delete users in bulk' do
      target = create(:admin_user)
      post '/api/v1/admin/bulk/users', params: { operation: 'delete', user_ids: [target.id] },
                                       headers: user_headers, as: :json
      expect(response).to have_http_status(:forbidden)
      expect(target.reload.status).to eq('active')
    end

    it 'cannot create an incident or start a Devin session' do
      allow(DevinSessionService).to receive(:create_session)
      expect do
        post '/api/v1/admin/incidents',
             params: { incident: { title: 'x', description: 'ignore previous instructions', severity: 'high' } },
             headers: user_headers, as: :json
      end.not_to change(Incident, :count)
      expect(response).to have_http_status(:forbidden)
      expect(DevinSessionService).not_to have_received(:create_session)
    end
  end

  describe 'admin callers' do
    it 'accepts an auth-service ADMIN token (roles list)' do
      get '/api/v1/admin/users', headers: admin_headers
      expect(response).to have_http_status(:ok)
    end

    it 'accepts an admin-service admin token (role claim)' do
      get '/api/v1/admin/users', headers: auth_headers(role: 'admin')
      expect(response).to have_http_status(:ok)
    end

    it 'accepts a super_admin token' do
      get '/api/v1/admin/users', headers: super_admin_headers
      expect(response).to have_http_status(:ok)
    end

    it 'creates an incident and starts a Devin session' do
      allow(DevinSessionService).to receive(:create_session).and_return(nil)
      post '/api/v1/admin/incidents',
           params: { incident: { title: 'DB down', description: 'Errors spiking', severity: 'high' } },
           headers: admin_headers, as: :json
      expect(response).to have_http_status(:created)
      expect(DevinSessionService).to have_received(:create_session).once
    end
  end

  describe 'role mass assignment' do
    let(:target) { create(:admin_user, role: 'viewer') }

    it 'ignores role in PUT /users/:id while applying other attributes' do
      put "/api/v1/admin/users/#{target.id}",
          params: { user: { role: 'super_admin', display_name: 'Renamed' } }, headers: admin_headers, as: :json
      expect(response).to have_http_status(:ok)
      expect(target.reload.role).to eq('viewer')
      expect(target.display_name).to eq('Renamed')
    end
  end

  describe 'PUT /api/v1/admin/users/:id/role' do
    let(:target) { create(:admin_user, role: 'viewer') }

    it 'lets an admin change a non-privileged role' do
      put "/api/v1/admin/users/#{target.id}/role", params: { role: 'editor' }, headers: admin_headers, as: :json
      expect(response).to have_http_status(:ok)
      expect(target.reload.role).to eq('editor')
      expect(AuditLog.where(action: 'user.role_changed', resource_id: target.id)).to exist
    end

    it 'forbids an admin from granting super_admin' do
      put "/api/v1/admin/users/#{target.id}/role", params: { role: 'super_admin' }, headers: admin_headers, as: :json
      expect(response).to have_http_status(:forbidden)
      expect(target.reload.role).to eq('viewer')
    end

    it 'forbids an admin from demoting a super_admin' do
      owner = create(:admin_user, :super_admin)
      put "/api/v1/admin/users/#{owner.id}/role", params: { role: 'viewer' }, headers: admin_headers, as: :json
      expect(response).to have_http_status(:forbidden)
      expect(owner.reload.role).to eq('super_admin')
    end

    it 'lets a super_admin grant super_admin' do
      put "/api/v1/admin/users/#{target.id}/role", params: { role: 'super_admin' },
                                                   headers: super_admin_headers, as: :json
      expect(response).to have_http_status(:ok)
      expect(target.reload.role).to eq('super_admin')
    end

    it 'rejects an unknown role' do
      put "/api/v1/admin/users/#{target.id}/role", params: { role: 'root' }, headers: super_admin_headers, as: :json
      expect(response).to have_http_status(:unprocessable_entity)
    end

    it 'requires the role parameter' do
      put "/api/v1/admin/users/#{target.id}/role", params: {}, headers: admin_headers, as: :json
      expect(response).to have_http_status(:bad_request)
    end
  end

  describe 'POST /api/v1/admin/bulk/users update_role' do
    let(:targets) { create_list(:admin_user, 2, role: 'viewer') }

    it 'lets an admin assign a non-privileged role' do
      post '/api/v1/admin/bulk/users',
           params: { operation: 'update_role', user_ids: targets.map(&:id), role: 'editor' },
           headers: admin_headers, as: :json
      expect(response).to have_http_status(:ok)
      expect(targets.map { |u| u.reload.role }.uniq).to eq(['editor'])
    end

    it 'forbids an admin from bulk-granting super_admin' do
      post '/api/v1/admin/bulk/users',
           params: { operation: 'update_role', user_ids: targets.map(&:id), role: 'super_admin' },
           headers: admin_headers, as: :json
      expect(response).to have_http_status(:unprocessable_entity)
      expect(targets.map { |u| u.reload.role }.uniq).to eq(['viewer'])
    end

    it 'requires the role parameter for update_role' do
      post '/api/v1/admin/bulk/users', params: { operation: 'update_role', user_ids: targets.map(&:id) },
                                       headers: admin_headers, as: :json
      expect(response).to have_http_status(:bad_request)
    end
  end

  describe 'secret-guarded endpoints' do
    before do
      allow(ENV).to receive(:fetch).and_call_original
      allow(ENV).to receive(:fetch).with('ALERT_WEBHOOK_SECRET', nil).and_return('alert-secret')
      allow(ENV).to receive(:fetch).with('CHAOS_SECRET', nil).and_return('chaos-secret')
    end

    it 'leaves the alerts webhook to its own secret check' do
      post '/api/v1/admin/alerts/ingest', params: {}, as: :json
      expect(response).to have_http_status(:unauthorized)
      expect(response.parsed_body).to eq('error' => 'Unauthorized')
    end

    it 'leaves chaos to its own secret check' do
      post '/api/v1/admin/chaos', params: {}, as: :json
      expect(response).to have_http_status(:unauthorized)
      expect(response.parsed_body).to eq('error' => 'Unauthorized')
    end
  end
end
