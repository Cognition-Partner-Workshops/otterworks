require 'rails_helper'

RSpec.describe Api::V1::Admin::SettingsController do
  let(:redis) { instance_double(Redis, get: nil, set: 'OK', close: nil) }
  before do
    set_jwt_env(request)
    allow(Redis).to receive(:new).and_return(redis)
  end

  it 'reads the enabled default' do
    get :auto_investigate
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)).to eq('enabled' => true)
  end

  it 'writes a disabled toggle and returns the saved value' do
    expect(redis).to receive(:set).with('admin:auto_investigate', 'false') do
      allow(redis).to receive(:get).with('admin:auto_investigate').and_return('false')
    end
    put :update_auto_investigate, params: { enabled: false }
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)).to eq('enabled' => false)
  end

  it 'rejects a missing toggle' do
    put :update_auto_investigate
    expect(response).to have_http_status(:bad_request)
    expect(JSON.parse(response.body)['error']).to eq('Missing required parameter: enabled')
  end

  it 'rejects an invalid boolean rather than enabling investigation' do
    pending 'BUG: app/controllers/api/v1/admin/settings_controller.rb:12 casts arbitrary strings to true instead of rejecting invalid booleans'
    put :update_auto_investigate, params: { enabled: 'not-a-boolean' }
    expect(response.status).to be_between(400, 499)
  end

  it 'returns enabled when Redis reads fail' do
    allow(redis).to receive(:get).and_raise(Redis::BaseError, 'unavailable')
    get :auto_investigate
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)).to eq('enabled' => true)
  end

  it 'returns an error response when Redis writes fail' do
    allow(redis).to receive(:set).and_raise(Redis::BaseError, 'unavailable')
    put :update_auto_investigate, params: { enabled: true }
    expect(response).to have_http_status(:internal_server_error)
    expect(JSON.parse(response.body)).to eq('error' => 'Internal server error')
  end
end
