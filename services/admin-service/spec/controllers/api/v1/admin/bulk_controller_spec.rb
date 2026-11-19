require 'rails_helper'

RSpec.describe Api::V1::Admin::BulkController do
  before { set_jwt_env(request) }

  describe 'POST #users' do
    it 'keeps successful changes when another user fails and audits the counts' do
      good = create(:admin_user)
      bad = create(:admin_user)
      allow_any_instance_of(AdminUser).to receive(:suspend!).and_wrap_original do |method, **args|
        raise ActiveRecord::RecordInvalid, method.receiver if method.receiver.id == bad.id

        method.call(**args)
      end
      post :users, params: { operation: 'suspend', user_ids: [good.id, bad.id], reason: 'Policy' }
      expect(response).to have_http_status(:multi_status)
      body = JSON.parse(response.body)
      expect(body).to include('success_count' => 1, 'failure_count' => 1)
      expect(body['errors'].first['user_id']).to eq(bad.id)
      expect(good.reload.status).to eq('suspended')
      expect(bad.reload.status).to eq('active')
      expect(AuditLog.last.changes_made).to include('success' => 1, 'failures' => 1)
    end

    let!(:users) { create_list(:admin_user, 3) }
    let(:user_ids) { users.map(&:id) }

    it 'suspends multiple users' do
      post :users, params: { operation: 'suspend', user_ids: user_ids, reason: 'Policy' }
      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body['success_count']).to eq(3)
      expect(body['failure_count']).to eq(0)
    end

    it 'activates multiple users' do
      users.each(&:suspend!)
      post :users, params: { operation: 'activate', user_ids: user_ids }
      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body['success_count']).to eq(3)
    end

    it 'returns multi_status when some users not found' do
      post :users, params: { operation: 'suspend', user_ids: user_ids + [SecureRandom.uuid] }
      expect(response).to have_http_status(:multi_status)
      body = JSON.parse(response.body)
      expect(body['failure_count']).to eq(1)
    end

    it 'returns bad_request for empty user_ids' do
      post :users, params: { operation: 'suspend', user_ids: [] }
      expect(response).to have_http_status(:bad_request)
    end
  end
end
