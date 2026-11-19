require 'rails_helper'

RSpec.describe Api::V1::Admin::ChaosController do
  let(:redis) { instance_double(Redis, setex: 'OK', keys: [], del: 1) }
  before do
    allow(ENV).to receive(:fetch).and_call_original
    allow(ENV).to receive(:fetch).with('CHAOS_SECRET', nil).and_return('chaos-secret')
    request.headers['X-Chaos-Secret'] = 'chaos-secret'
    allow(Redis).to receive(:new).and_return(redis)
    allow(ChaosProbeService).to receive(:start)
  end

  it 'rejects the wrong secret without setting flags' do
    request.headers['X-Chaos-Secret'] = 'wrong'
    expect(redis).not_to receive(:setex)
    post :trigger, params: { service: 'search-service', scenario: 'suggest_500' }
    expect(response).to have_http_status(:unauthorized)
    expect(JSON.parse(response.body)).to eq('error' => 'Unauthorized')
  end

  it 'rejects an unlisted scenario without starting probes' do
    expect(ChaosProbeService).not_to receive(:start)
    post :trigger, params: { service: 'search-service', scenario: 'unknown' }
    expect(response).to have_http_status(:unprocessable_entity)
    expect(JSON.parse(response.body)['error']).to eq('Invalid service/scenario combination')
  end

  it 'sets the allowed flag with a ten-minute TTL for an authorized request' do
    expect(redis).to receive(:setex).with('chaos:search-service:suggest_500', 600, '1')
    post :trigger, params: { service: 'search-service', scenario: 'suggest_500' }
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)).to include('status' => 'chaos_active', 'expires_in' => 600, 'key' => 'chaos:search-service:suggest_500')
  end

  it 'clears flags and resolves active chaos-service incidents' do
    key = 'chaos:search-service:suggest_500'
    allow(redis).to receive(:keys).with('chaos:*').and_return([key])
    expect(redis).to receive(:del).with(key)
    incident = create(:incident)
    other = create(:incident, affected_service: 'auth-service')
    delete :reset
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)).to include('cleared' => [key], 'resolved_incidents' => [incident.id])
    expect(incident.reload.status).to eq('resolved')
    expect(other.reload.status).to eq('open')
  end

  it 'resets safely when no flags or incidents exist' do
    delete :reset
    expect(JSON.parse(response.body)).to include('cleared' => [], 'resolved_incidents' => [])
  end
end
