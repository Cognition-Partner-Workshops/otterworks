require 'rails_helper'

RSpec.describe Api::V1::Admin::AuditLogsController do
  before { set_jwt_env(request) }

  describe 'GET #index' do
    %i[since until].each do |filter|
      it "rejects malformed #{filter} dates" do
        get :index, params: { filter => 'not-a-date' }
        expect(response).to have_http_status(:bad_request)
        expect(JSON.parse(response.body)).to eq('error' => 'Invalid date format: not-a-date')
      end
    end

    it 'combines actor, resource and date filters' do
      matching = create(:audit_log, created_at: 1.day.ago)
      create(:audit_log, actor_id: matching.actor_id, resource_id: matching.resource_id, created_at: 10.days.ago)
      get :index, params: { actor_id: matching.actor_id, resource_type: matching.resource_type,
                            resource_id: matching.resource_id, since: 2.days.ago.iso8601, until: Time.current.iso8601 }
      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body)['audit_logs'].map { |l| l['id'] }).to eq([matching.id])
    end

    let!(:logs) { create_list(:audit_log, 3) }

    it 'returns paginated audit logs' do
      get :index
      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body['audit_logs'].length).to eq(3)
    end

    it 'filters by action type' do
      create(:audit_log, action: 'feature_flag.created')
      get :index, params: { action_type: 'feature_flag.created' }
      body = JSON.parse(response.body)
      expect(body['audit_logs'].all? { |l| l['action'] == 'feature_flag.created' }).to be true
    end

    it 'filters by resource type' do
      get :index, params: { resource_type: 'AdminUser' }
      body = JSON.parse(response.body)
      expect(body['audit_logs'].all? { |l| l['resource_type'] == 'AdminUser' }).to be true
    end
  end

  describe 'GET #show' do
    let(:log) { create(:audit_log) }

    it 'returns the audit log entry' do
      get :show, params: { id: log.id }
      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body['id']).to eq(log.id)
    end
  end
end
