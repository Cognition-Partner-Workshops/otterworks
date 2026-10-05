require 'rails_helper'

RSpec.describe Api::V1::Admin::StorageController do
  before { set_jwt_env(request) }

  describe 'GET #usage' do
    let!(:users) { create_list(:admin_user, 2) }
    let(:owner_ids) { users.map(&:id) }

    before do
      allow(AdminUser).to receive(:pluck).with(:id).and_return(owner_ids)
      allow(FileUsageClient).to receive(:usage).with(owner_ids).and_return(
        total_bytes: 4096,
        file_count: 2,
        owners: [
          { owner_id: owner_ids.first, file_count: 2, total_bytes: 4096 },
          { owner_id: owner_ids.second, file_count: 0, total_bytes: 0 }
        ]
      )
    end

    it 'returns aggregated storage usage for all users, including zeroes' do
      get :usage

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body['total_bytes']).to eq(4096)
      expect(body['file_count']).to eq(2)
      expect(Time.iso8601(body['generated_at'])).to be_a(Time)
      expect(body['users']).to eq([
        { 'user_id' => owner_ids.first, 'file_count' => 2, 'total_bytes' => 4096 },
        { 'user_id' => owner_ids.second, 'file_count' => 0, 'total_bytes' => 0 }
      ])
      expect(FileUsageClient).to have_received(:usage).with(owner_ids)
    end

    it 'returns 502 when the file service is unavailable' do
      allow(FileUsageClient).to receive(:usage).and_raise(FileUsageClient::Error, 'connection refused')
      expect(Rails.logger).to receive(:error).with('File usage request failed: connection refused')

      get :usage

      expect(response).to have_http_status(:bad_gateway)
      expect(JSON.parse(response.body)).to eq('error' => 'File service unavailable')
    end
  end
end
