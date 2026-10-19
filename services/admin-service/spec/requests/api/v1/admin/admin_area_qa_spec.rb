require 'rails_helper'

# End-to-end request specs for the admin area (JWT middleware -> controllers -> DB).
RSpec.describe 'Admin area QA', type: :request do
  def middleware_secret
    Rails.application.credentials.jwt_secret || ENV.fetch('JWT_SECRET', Rails.application.secrets.jwt_secret)
  end

  def bearer(role: 'super_admin', exp: 1.hour.from_now, secret: middleware_secret, sub: SecureRandom.uuid)
    token = JWT.encode({ sub: sub, email: 'qa@otterworks.test', role: role, exp: exp.to_i, iat: Time.current.to_i },
                       secret, 'HS256')
    { 'Authorization' => "Bearer #{token}" }
  end

  def json
    JSON.parse(response.body)
  end

  describe 'JWT authentication' do
    it 'rejects requests without a token' do
      get '/api/v1/admin/features'
      expect(response).to have_http_status(:unauthorized)
      expect(json['error']).to eq('Missing authorization token')
    end

    it 'rejects a token signed with the wrong secret' do
      get '/api/v1/admin/features', headers: bearer(secret: SecureRandom.hex(32))
      expect(response).to have_http_status(:unauthorized)
      expect(json['error']).to eq('Invalid or expired token')
    end

    it 'rejects an expired token' do
      get '/api/v1/admin/features', headers: bearer(exp: 1.minute.ago)
      expect(response).to have_http_status(:unauthorized)
    end

    it 'rejects a non-Bearer authorization scheme' do
      get '/api/v1/admin/features', headers: { 'Authorization' => 'Basic YWRtaW46YWRtaW4=' }
      expect(response).to have_http_status(:unauthorized)
    end

    it 'accepts a valid admin token' do
      get '/api/v1/admin/features', headers: bearer
      expect(response).to have_http_status(:ok)
    end

    it 'leaves /health and /metrics public' do
      get '/health'
      expect(response).to have_http_status(:ok)
      get '/metrics'
      expect(response).to have_http_status(:ok)
    end

    it 'forbids a plain USER token from admin endpoints' do
      pending '[REAL] admin-service has no admin role check: any valid JWT (role USER) can manage users/flags'
      get '/api/v1/admin/users', headers: bearer(role: 'USER')
      expect(response).to have_http_status(:forbidden)
    end
  end

  describe 'feature flags' do
    let!(:flag) { create(:feature_flag, name: 'qa_toggle_flag', enabled: false) }

    it 'toggles a flag on and back off, persisting each state' do
      put "/api/v1/admin/features/#{flag.id}", params: { feature: { enabled: true } }, headers: bearer, as: :json
      expect(response).to have_http_status(:ok)
      expect(json['enabled']).to be true
      expect(flag.reload.enabled).to be true

      put "/api/v1/admin/features/#{flag.id}", params: { feature: { enabled: false } }, headers: bearer, as: :json
      expect(json['enabled']).to be false
      expect(flag.reload.enabled).to be false
    end

    it 'writes a feature_flag.updated audit entry with the actor and before/after state' do
      actor = SecureRandom.uuid
      expect do
        put "/api/v1/admin/features/#{flag.id}", params: { feature: { enabled: true } },
                                                 headers: bearer(sub: actor), as: :json
      end.to change(AuditLog, :count).by(1)
      entry = AuditLog.order(:created_at).last
      expect(entry.action).to eq('feature_flag.updated')
      expect(entry.resource_id).to eq(flag.id)
      expect(entry.actor_id).to eq(actor)
      expect(entry.changes_made.dig('before', 'enabled')).to be false
      expect(entry.changes_made.dig('after', 'enabled')).to be true
    end

    it 'filters index by enabled=false' do
      create(:feature_flag, :enabled)
      get '/api/v1/admin/features', params: { enabled: 'false' }, headers: bearer
      expect(json['features'].map { |f| f['enabled'] }.uniq).to eq([false])
    end

    it 'returns 404 for an unknown flag' do
      put "/api/v1/admin/features/#{SecureRandom.uuid}", params: { feature: { enabled: true } }, headers: bearer,
                                                          as: :json
      expect(response).to have_http_status(:not_found)
    end

    it 'accepts an unwrapped JSON body via Rails params wrapping' do
      put "/api/v1/admin/features/#{flag.id}", params: { enabled: true }, headers: bearer, as: :json
      expect(response).to have_http_status(:ok)
      expect(flag.reload.enabled).to be(true)
    end

    it 'rejects an out-of-range rollout percentage' do
      put "/api/v1/admin/features/#{flag.id}", params: { feature: { rollout_percentage: 150 } }, headers: bearer,
                                                as: :json
      expect(response).to have_http_status(:unprocessable_entity)
    end
  end

  describe 'audit log filters' do
    let(:actor) { SecureRandom.uuid }

    before do
      create(:audit_log, action: 'user.suspended', actor_id: actor, created_at: 3.days.ago)
      create(:audit_log, action: 'feature_flag.updated', resource_type: 'FeatureFlag', created_at: 1.day.ago)
      create(:audit_log, action: 'user.updated', created_at: 1.hour.ago)
    end

    it 'returns newest first with pagination metadata and headers' do
      get '/api/v1/admin/audit-logs', headers: bearer
      expect(response).to have_http_status(:ok)
      times = json['audit_logs'].map { |l| Time.zone.parse(l['created_at']) }
      expect(times).to eq(times.sort.reverse)
      expect(json).to include('total' => 3, 'page' => 1, 'per_page' => 20)
      expect(response.headers['X-Total-Count']).to eq('3')
    end

    it 'filters by action_type' do
      get '/api/v1/admin/audit-logs', params: { action_type: 'user.suspended' }, headers: bearer
      expect(json['audit_logs'].map { |l| l['action'] }).to eq(['user.suspended'])
    end

    it 'filters by actor_id' do
      get '/api/v1/admin/audit-logs', params: { actor_id: actor }, headers: bearer
      expect(json['audit_logs'].map { |l| l['actor_id'] }).to eq([actor])
    end

    it 'filters by resource_type' do
      get '/api/v1/admin/audit-logs', params: { resource_type: 'FeatureFlag' }, headers: bearer
      expect(json['total']).to eq(1)
    end

    it 'filters by since/until window' do
      get '/api/v1/admin/audit-logs', params: { since: 2.days.ago.iso8601, until: 2.hours.ago.iso8601 },
                                      headers: bearer
      expect(json['audit_logs'].map { |l| l['action'] }).to eq(['feature_flag.updated'])
    end

    it 'returns 400 for an invalid date' do
      get '/api/v1/admin/audit-logs', params: { since: 'not-a-date' }, headers: bearer
      expect(response).to have_http_status(:bad_request)
      expect(json['error']).to include('Invalid date format')
    end

    it 'clamps per_page to 100 and paginates' do
      get '/api/v1/admin/audit-logs', params: { per_page: 1000 }, headers: bearer
      expect(json['per_page']).to eq(100)
      get '/api/v1/admin/audit-logs', params: { per_page: 2, page: 2 }, headers: bearer
      expect(json['audit_logs'].length).to eq(1)
    end
  end

  describe 'users management' do
    let!(:user) { create(:admin_user) }

    it 'suspends and re-activates a user, auditing both' do
      put "/api/v1/admin/users/#{user.id}/suspend", headers: bearer
      expect(response).to have_http_status(:ok)
      expect(user.reload.status).to eq('suspended')
      put "/api/v1/admin/users/#{user.id}/activate", headers: bearer
      expect(response).to have_http_status(:ok)
      expect(user.reload.status).to eq('active')
      expect(AuditLog.where(resource_id: user.id).count).to be >= 2
    end

    it 'searches users by email' do
      get '/api/v1/admin/users', params: { q: user.email }, headers: bearer
      expect(response).to have_http_status(:ok)
      expect(json['users'].map { |u| u['id'] }).to include(user.id)
    end
  end

  describe 'health and metrics' do
    it 'reports database connectivity on /health' do
      get '/health'
      expect(json).to include('status' => 'healthy', 'database' => 'connected')
    end

    it 'exposes feature-flag gauges on /metrics' do
      create(:feature_flag, :enabled)
      create(:feature_flag)
      get '/metrics'
      expect(response.body).to include('admin_feature_flags_total 2')
      expect(response.body).to include('admin_feature_flags_enabled 1')
    end
  end
end
