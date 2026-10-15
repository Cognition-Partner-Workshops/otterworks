require 'rails_helper'

RSpec.describe Api::V1::Admin::UsersController, type: :controller do
  before { set_jwt_env(request, user_id: actor_id, email: 'qa-admin@otterworks.dev') }

  let(:actor_id) { SecureRandom.uuid }

  def body
    JSON.parse(response.body)
  end

  describe 'search and listing' do
    it 'searches by display name case-insensitively' do
      match = create(:admin_user, display_name: 'Otter Searchable')
      create(:admin_user, display_name: 'Someone Else')
      get :index, params: { q: 'otter SEARCH' }
      expect(body['users'].map { |u| u['id'] }).to eq([match.id])
    end

    it 'treats LIKE wildcards in the query literally' do
      create(:admin_user, display_name: 'Plain Name')
      get :index, params: { q: '%' }
      expect(body['users']).to be_empty
    end

    it 'paginates and sets pagination headers' do
      create_list(:admin_user, 5)
      get :index, params: { page: 2, per_page: 2 }
      expect(body['users'].length).to eq(2)
      expect(body['page']).to eq(2)
      expect(response.headers['X-Total-Count']).to eq('5')
      expect(response.headers['X-Per-Page']).to eq('2')
    end

    it 'clamps per_page to 100' do
      get :index, params: { per_page: 1000 }
      expect(body['per_page']).to eq(100)
    end

    it 'embeds the storage quota of each user' do
      user = create(:admin_user)
      create(:storage_quota, user_id: user.id)
      get :index
      quota = body['users'].first['storage_quota']
      expect(quota['user_id']).to eq(user.id)
      expect(quota['usage_percentage']).to eq(20.0)
    end

    it 'combines role and status filters' do
      create(:admin_user, :editor)
      target = create(:admin_user, :editor, :suspended)
      create(:admin_user, :suspended)
      get :index, params: { role: 'editor', status: 'suspended' }
      expect(body['users'].map { |u| u['id'] }).to eq([target.id])
    end
  end

  describe 'suspend / activate' do
    let(:user) { create(:admin_user) }

    it 'suspends with a reason and writes an audit log' do
      expect { put :suspend, params: { id: user.id, reason: 'abuse' } }.to change(AuditLog, :count).by(1)
      expect(body['status']).to eq('suspended')
      expect(body['suspended_reason']).to eq('abuse')
      expect(body['suspended_at']).to be_present
      log = AuditLog.last
      expect(log.action).to eq('user.suspended')
      expect(log.actor_id).to eq(actor_id)
      expect(log.changes_made).to eq('reason' => 'abuse')
    end

    it 'activates a suspended user and clears suspension fields' do
      suspended = create(:admin_user, :suspended)
      put :activate, params: { id: suspended.id }
      expect(body['status']).to eq('active')
      expect(body['suspended_at']).to be_nil
      expect(body['suspended_reason']).to be_nil
      expect(AuditLog.last.action).to eq('user.activated')
    end

    it 'returns 404 when suspending an unknown user' do
      put :suspend, params: { id: SecureRandom.uuid }
      expect(response).to have_http_status(:not_found)
    end
  end

  describe 'role edit' do
    let(:user) { create(:admin_user, role: 'viewer') }

    %w[super_admin admin editor viewer].each do |role|
      it "accepts role #{role}" do
        put :update, params: { id: user.id, user: { role: role } }
        expect(response).to have_http_status(:ok)
        expect(body['role']).to eq(role)
      end
    end

    it 'audits the before/after role' do
      put :update, params: { id: user.id, user: { role: 'editor' } }
      log = AuditLog.find_by!(action: 'user.updated', resource_id: user.id)
      expect(log.changes_made['before']['role']).to eq('viewer')
      expect(log.changes_made['after']['role']).to eq('editor')
    end

    it 'does not audit a rejected update' do
      expect { put :update, params: { id: user.id, user: { role: 'root' } } }.not_to change(AuditLog, :count)
      expect(user.reload.role).to eq('viewer')
    end

    it 'rejects a duplicate email' do
      other = create(:admin_user)
      put :update, params: { id: user.id, user: { email: other.email } }
      expect(response).to have_http_status(:unprocessable_entity)
    end

    it 'ignores non-permitted attributes such as status' do
      put :update, params: { id: user.id, user: { display_name: 'Renamed', status: 'deleted' } }
      expect(body['display_name']).to eq('Renamed')
      expect(user.reload.status).to eq('active')
    end

    it 'returns 400 without a user payload' do
      put :update, params: { id: user.id }
      expect(response).to have_http_status(:bad_request)
    end
  end

  it 'audits soft delete' do
    user = create(:admin_user)
    delete :destroy, params: { id: user.id }
    expect(AuditLog.last.action).to eq('user.deleted')
    expect(AdminUser.find(user.id).status).to eq('deleted')
  end
end
