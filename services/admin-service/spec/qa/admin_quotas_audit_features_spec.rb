require 'rails_helper'

RSpec.describe Api::V1::Admin::QuotasController, type: :controller do
  before { set_jwt_env(request) }

  let(:user_id) { SecureRandom.uuid }
  let!(:quota) { create(:storage_quota, user_id: user_id) }

  it 'returns usage fields' do
    get :show, params: { user_id: user_id }
    body = JSON.parse(response.body)
    expect(body['usage_percentage']).to eq(20.0)
    expect(body['over_quota']).to be false
    expect(body['remaining_bytes']).to eq(4_294_967_296)
  end

  it 'audits a quota update with before/after' do
    put :update, params: { user_id: user_id, quota: { quota_bytes: 10_737_418_240 } }
    expect(response).to have_http_status(:ok)
    log = AuditLog.find_by!(action: 'quota.updated')
    expect(log.changes_made['before']['quota_bytes']).to eq(5_368_709_120)
    expect(log.changes_made['after']['quota_bytes']).to eq(10_737_418_240)
  end

  it 'rejects a zero quota' do
    put :update, params: { user_id: user_id, quota: { quota_bytes: 0 } }
    expect(response).to have_http_status(:unprocessable_entity)
  end

  it 'reports over_quota when the new quota is below usage' do
    put :update, params: { user_id: user_id, quota: { quota_bytes: 1_000 } }
    body = JSON.parse(response.body)
    expect(body['over_quota']).to be true
    expect(body['remaining_bytes']).to eq(0)
  end

  it 'returns 404 when updating a user with no quota row' do
    put :update, params: { user_id: SecureRandom.uuid, quota: { quota_bytes: 1 } }
    expect(response).to have_http_status(:not_found)
  end
end

RSpec.describe Api::V1::Admin::AuditLogsController, type: :controller do
  before { set_jwt_env(request) }

  def ids
    JSON.parse(response.body)['audit_logs'].map { |l| l['id'] }
  end

  it 'orders newest first' do
    old = create(:audit_log, created_at: 2.days.ago)
    recent = create(:audit_log, created_at: 1.hour.ago)
    get :index
    expect(ids).to eq([recent.id, old.id])
  end

  it 'filters by actor' do
    actor = SecureRandom.uuid
    mine = create(:audit_log, actor_id: actor)
    create(:audit_log)
    get :index, params: { actor_id: actor }
    expect(ids).to eq([mine.id])
  end

  it 'filters by resource type and id' do
    target = create(:audit_log, resource_type: 'FeatureFlag')
    create(:audit_log, resource_type: 'FeatureFlag')
    get :index, params: { resource_type: 'FeatureFlag', resource_id: target.resource_id }
    expect(ids).to eq([target.id])
  end

  it 'filters by since/until window' do
    create(:audit_log, created_at: 10.days.ago)
    inside = create(:audit_log, created_at: 3.days.ago)
    create(:audit_log, created_at: 1.hour.ago)
    get :index, params: { since: 5.days.ago.iso8601, until: 2.days.ago.iso8601 }
    expect(ids).to eq([inside.id])
  end

  it 'returns 400 for an invalid since date' do
    get :index, params: { since: 'not-a-date' }
    expect(response).to have_http_status(:bad_request)
    expect(JSON.parse(response.body)['error']).to include('Invalid date format')
  end

  it 'returns 404 for an unknown audit log' do
    get :show, params: { id: SecureRandom.uuid }
    expect(response).to have_http_status(:not_found)
  end

  it 'paginates' do
    create_list(:audit_log, 3)
    get :index, params: { per_page: 2 }
    body = JSON.parse(response.body)
    expect(body['audit_logs'].length).to eq(2)
    expect(body['total']).to eq(3)
  end
end

RSpec.describe Api::V1::Admin::FeaturesController, type: :controller do
  before { set_jwt_env(request) }

  it 'filters disabled flags' do
    create(:feature_flag, :enabled)
    off = create(:feature_flag)
    get :index, params: { enabled: 'false' }
    expect(JSON.parse(response.body)['features'].map { |f| f['id'] }).to eq([off.id])
  end

  it 'audits a toggle with before/after' do
    flag = create(:feature_flag)
    put :update, params: { id: flag.id, feature: { enabled: true } }
    log = AuditLog.find_by!(action: 'feature_flag.updated', resource_id: flag.id)
    expect(log.changes_made['before']['enabled']).to be false
    expect(log.changes_made['after']['enabled']).to be true
  end

  it 'rejects a rollout percentage over 100' do
    flag = create(:feature_flag)
    put :update, params: { id: flag.id, feature: { rollout_percentage: 150 } }
    expect(response).to have_http_status(:unprocessable_entity)
  end

  it 'rejects a duplicate flag name' do
    flag = create(:feature_flag)
    post :create, params: { feature: { name: flag.name } }
    expect(response).to have_http_status(:unprocessable_entity)
  end

  it 'returns 404 for an unknown flag' do
    put :update, params: { id: SecureRandom.uuid, feature: { enabled: true } }
    expect(response).to have_http_status(:not_found)
  end

  it 'audits deletion' do
    flag = create(:feature_flag)
    delete :destroy, params: { id: flag.id }
    expect(AuditLog.last.action).to eq('feature_flag.deleted')
  end
end
