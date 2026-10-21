require 'rails_helper'

RSpec.describe Api::V1::Admin::ChaosController do
  let(:secret) { 'test-chaos-secret' }
  let(:redis) { instance_double(Redis, setex: 'OK', keys: ['chaos:search-service:suggest_500'], del: 1) }
  let(:params) { { service: 'search-service', scenario: 'suggest_500' } }

  around do |example|
    original = ENV.fetch('CHAOS_SECRET', nil)
    example.run
  ensure
    ENV['CHAOS_SECRET'] = original
  end

  before do
    set_jwt_env(request)
    allow(Redis).to receive(:new).and_return(redis)
    allow(ChaosProbeService).to receive(:start)
  end

  def trigger(headers = {})
    request.headers.merge!(headers)
    post :trigger, params: params, as: :json
  end

  def reset(headers = {})
    request.headers.merge!(headers)
    delete :reset
  end

  shared_examples 'a rejected chaos request' do |status|
    it "POST responds #{status} without setting a chaos flag" do
      trigger(headers)
      expect(response).to have_http_status(status)
      expect(redis).not_to have_received(:setex)
      expect(ChaosProbeService).not_to have_received(:start)
    end

    it "DELETE responds #{status} without clearing flags or resolving incidents" do
      incident = Incident.create!(title: 'chaos', description: 'chaos', severity: 'high',
                                  status: 'open', affected_service: 'search-service')
      reset(headers)
      expect(response).to have_http_status(status)
      expect(redis).not_to have_received(:del)
      expect(incident.reload.status).to eq('open')
    end
  end

  context 'when CHAOS_SECRET is unset' do
    before { ENV.delete('CHAOS_SECRET') }

    it_behaves_like 'a rejected chaos request', :service_unavailable do
      let(:headers) { {} }
    end
  end

  context 'when CHAOS_SECRET is empty' do
    before { ENV['CHAOS_SECRET'] = '' }

    it_behaves_like 'a rejected chaos request', :service_unavailable do
      let(:headers) { { 'X-Chaos-Secret' => '' } }
    end
  end

  context 'when CHAOS_SECRET is configured' do
    before { ENV['CHAOS_SECRET'] = secret }

    context 'without X-Chaos-Secret' do
      it_behaves_like 'a rejected chaos request', :unauthorized do
        let(:headers) { {} }
      end
    end

    context 'with a wrong X-Chaos-Secret' do
      it_behaves_like 'a rejected chaos request', :unauthorized do
        let(:headers) { { 'X-Chaos-Secret' => 'wrong-secret' } }
      end
    end

    it 'POST with the correct secret activates chaos' do
      trigger('X-Chaos-Secret' => secret)
      expect(response).to have_http_status(:ok)
      expect(response.parsed_body).to include('status' => 'chaos_active', 'key' => 'chaos:search-service:suggest_500')
      expect(redis).to have_received(:setex).with('chaos:search-service:suggest_500', anything, '1')
      expect(ChaosProbeService).to have_received(:start).with(service: 'search-service',
                                                              redis_key: 'chaos:search-service:suggest_500')
    end

    it 'DELETE with the correct secret clears flags and resolves chaos incidents' do
      incident = Incident.create!(title: 'chaos', description: 'chaos', severity: 'high',
                                  status: 'open', affected_service: 'search-service')
      reset('X-Chaos-Secret' => secret)
      expect(response).to have_http_status(:ok)
      expect(redis).to have_received(:del).with('chaos:search-service:suggest_500')
      expect(incident.reload.status).to eq('resolved')
    end
  end
end
