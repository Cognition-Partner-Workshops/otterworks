require 'rails_helper'

RSpec.describe Api::V1::Admin::SettingsController do
  before { set_jwt_env(request) }

  describe 'GET #auto_investigate' do
    [true, false].each do |value|
      it "returns enabled=#{value}" do
        allow(AdminSettingsService).to receive(:auto_investigate_enabled?).and_return(value)
        get :auto_investigate
        expect(response).to have_http_status(:ok)
        expect(JSON.parse(response.body)).to eq('enabled' => value)
      end
    end
  end

  describe 'PUT #update_auto_investigate' do
    before { allow(AdminSettingsService).to receive(:set_auto_investigate) }

    { 'false' => false, 'true' => true, '0' => false, '1' => true, false => false }.each do |input, cast|
      it "casts #{input.inspect} to #{cast}" do
        allow(AdminSettingsService).to receive(:auto_investigate_enabled?).and_return(cast)
        put :update_auto_investigate, params: { enabled: input }
        expect(response).to have_http_status(:ok)
        expect(AdminSettingsService).to have_received(:set_auto_investigate).with(cast)
        expect(JSON.parse(response.body)['enabled']).to eq(cast)
      end
    end

    it 'returns 400 when enabled is missing' do
      put :update_auto_investigate
      expect(response).to have_http_status(:bad_request)
      expect(AdminSettingsService).not_to have_received(:set_auto_investigate)
    end

    it 'returns 400 when enabled is blank' do
      put :update_auto_investigate, params: { enabled: '' }
      expect(response).to have_http_status(:bad_request)
    end

    it 'returns 500 when the settings store is unavailable' do
      allow(AdminSettingsService).to receive(:set_auto_investigate).and_raise(Redis::CannotConnectError)
      put :update_auto_investigate, params: { enabled: 'true' }
      expect(response).to have_http_status(:internal_server_error)
    end
  end
end
