require 'rails_helper'

RSpec.describe Api::V1::Admin::UsersController do
  let(:actor_id) { SecureRandom.uuid }

  before { set_jwt_env(request, user_id: actor_id, email: 'qa-actor@otterworks.io') }

  it 'suspends a user, stores the reason and audits it with the acting admin' do
    user = create(:admin_user)
    put :suspend, params: { id: user.id, reason: 'QA policy check' }
    expect(response).to have_http_status(:ok)
    body = JSON.parse(response.body)
    expect(body['status']).to eq('suspended')
    expect(body['suspended_reason']).to eq('QA policy check')
    log = AuditLog.find_by(action: 'user.suspended', resource_id: user.id)
    expect(log.actor_id).to eq(actor_id)
    expect(log.actor_email).to eq('qa-actor@otterworks.io')
    expect(log.changes_made).to eq('reason' => 'QA policy check')
  end

  it 'activates a suspended user and clears suspension fields' do
    user = create(:admin_user, :suspended)
    put :activate, params: { id: user.id }
    body = JSON.parse(response.body)
    expect(body['status']).to eq('active')
    expect(body['suspended_at']).to be_nil
    expect(body['suspended_reason']).to be_nil
    expect(AuditLog.where(action: 'user.activated', resource_id: user.id).count).to eq(1)
  end

  it 'soft-deletes instead of removing the row' do
    user = create(:admin_user)
    delete :destroy, params: { id: user.id }
    expect(response).to have_http_status(:no_content)
    expect(user.reload.status).to eq('deleted')
    expect(AuditLog.where(action: 'user.deleted', resource_id: user.id).count).to eq(1)
  end

  it 'returns 404 when suspending an unknown user' do
    put :suspend, params: { id: SecureRandom.uuid }
    expect(response).to have_http_status(:not_found)
  end

  it 'rejects an invalid role update with 422 and does not audit' do
    user = create(:admin_user)
    put :update, params: { id: user.id, user: { role: 'god_mode' } }
    expect(response).to have_http_status(:unprocessable_entity)
    expect(AuditLog.where(action: 'user.updated').count).to eq(0)
  end

  it 'records before/after when changing a role' do
    user = create(:admin_user)
    put :update, params: { id: user.id, user: { role: 'editor' } }
    log = AuditLog.find_by(action: 'user.updated', resource_id: user.id)
    expect(log.changes_made['before']['role']).to eq('viewer')
    expect(log.changes_made['after']['role']).to eq('editor')
  end

  it 'searches case-insensitively by display name' do
    create(:admin_user, display_name: 'Quinn Archer')
    create(:admin_user, display_name: 'Other Person')
    get :index, params: { q: 'quinn' }
    names = JSON.parse(response.body)['users'].map { |u| u['display_name'] }
    expect(names).to eq(['Quinn Archer'])
  end

  it 'treats LIKE wildcards in the search query literally' do
    create(:admin_user, display_name: 'Plain User')
    get :index, params: { q: '%' }
    expect(JSON.parse(response.body)['users']).to be_empty
  end

  it 'clamps per_page to 100 and sets pagination headers' do
    get :index, params: { per_page: 1000 }
    expect(JSON.parse(response.body)['per_page']).to eq(100)
    expect(response.headers['X-Per-Page']).to eq('100')
  end

  it 'falls back to page 1 for invalid page numbers' do
    get :index, params: { page: -3 }
    expect(JSON.parse(response.body)['page']).to eq(1)
  end
end
