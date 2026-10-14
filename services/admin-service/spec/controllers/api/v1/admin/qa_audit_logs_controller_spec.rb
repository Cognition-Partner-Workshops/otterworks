require 'rails_helper'

RSpec.describe Api::V1::Admin::AuditLogsController do
  before { set_jwt_env(request) }

  it 'returns logs newest first' do
    old = create(:audit_log, created_at: 2.days.ago)
    recent = create(:audit_log)
    get :index
    ids = JSON.parse(response.body)['audit_logs'].map { |l| l['id'] }
    expect(ids).to eq([recent.id, old.id])
  end

  it 'filters by action_type' do
    create(:audit_log, action: 'user.suspended')
    create(:audit_log, action: 'user.updated')
    get :index, params: { action_type: 'user.suspended' }
    actions = JSON.parse(response.body)['audit_logs'].map { |l| l['action'] }
    expect(actions).to eq(['user.suspended'])
  end

  it 'filters by actor_id' do
    actor = SecureRandom.uuid
    create(:audit_log, actor_id: actor)
    create(:audit_log)
    get :index, params: { actor_id: actor }
    expect(JSON.parse(response.body)['total']).to eq(1)
  end

  it 'filters by resource type and id' do
    target = create(:audit_log, resource_type: 'FeatureFlag')
    create(:audit_log, resource_type: 'FeatureFlag')
    get :index, params: { resource_type: 'FeatureFlag', resource_id: target.resource_id }
    expect(JSON.parse(response.body)['audit_logs'].map { |l| l['id'] }).to eq([target.id])
  end

  it 'applies since/until window' do
    create(:audit_log, created_at: 10.days.ago)
    inside = create(:audit_log, created_at: 3.days.ago)
    create(:audit_log)
    get :index, params: { since: 5.days.ago.iso8601, until: 1.day.ago.iso8601 }
    expect(JSON.parse(response.body)['audit_logs'].map { |l| l['id'] }).to eq([inside.id])
  end

  it 'returns 400 for an unparseable since date' do
    get :index, params: { since: 'not-a-date' }
    expect(response).to have_http_status(:bad_request)
    expect(JSON.parse(response.body)['error']).to include('Invalid date format')
  end

  it 'paginates' do
    create_list(:audit_log, 3)
    get :index, params: { per_page: 2, page: 2 }
    body = JSON.parse(response.body)
    expect(body['audit_logs'].size).to eq(1)
    expect(body['total']).to eq(3)
  end

  it 'shows a single entry and 404s on unknown ids' do
    log = create(:audit_log)
    get :show, params: { id: log.id }
    expect(JSON.parse(response.body)['id']).to eq(log.id)
    get :show, params: { id: SecureRandom.uuid }
    expect(response).to have_http_status(:not_found)
  end
end
