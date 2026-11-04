require 'rails_helper'

RSpec.describe Api::V1::Admin::ChaosController do
  let(:redis) { instance_double(Redis, setex: 'OK', keys: [], del: 0) }

  before do
    allow_any_instance_of(described_class).to receive(:redis).and_return(redis)
    allow(ChaosProbeService).to receive(:start)
  end

  describe 'POST #trigger' do
    let(:valid_params) { { service: 'search-service', scenario: 'suggest_500' } }

    context 'without a JWT' do
      it 'fails closed when CHAOS_SECRET is not configured' do
        with_env('CHAOS_SECRET' => nil) do
          post :trigger, params: valid_params
        end
        expect(response).to have_http_status(:unauthorized)
        expect(redis).not_to have_received(:setex)
      end

      it 'fails closed when CHAOS_SECRET is empty' do
        with_env('CHAOS_SECRET' => '') do
          request.headers['X-Chaos-Secret'] = ''
          post :trigger, params: valid_params
        end
        expect(response).to have_http_status(:unauthorized)
      end

      it 'rejects a wrong X-Chaos-Secret' do
        with_env('CHAOS_SECRET' => 'correct-secret') do
          request.headers['X-Chaos-Secret'] = 'wrong-secret'
          post :trigger, params: valid_params
        end
        expect(response).to have_http_status(:unauthorized)
      end

      it 'accepts the configured X-Chaos-Secret' do
        with_env('CHAOS_SECRET' => 'correct-secret') do
          request.headers['X-Chaos-Secret'] = 'correct-secret'
          post :trigger, params: valid_params
        end
        expect(response).to have_http_status(:ok)
        expect(redis).to have_received(:setex).with('chaos:search-service:suggest_500', 600, '1')
      end
    end

    context 'with an authenticated admin' do
      before { set_jwt_env(request) }

      it 'allows the request without a chaos secret' do
        with_env('CHAOS_SECRET' => nil) do
          post :trigger, params: valid_params
        end
        expect(response).to have_http_status(:ok)
      end
    end
  end

  describe 'DELETE #reset' do
    it 'fails closed without credentials' do
      with_env('CHAOS_SECRET' => nil) do
        delete :reset
      end
      expect(response).to have_http_status(:unauthorized)
    end

    it 'allows an authenticated admin' do
      set_jwt_env(request)
      delete :reset
      expect(response).to have_http_status(:ok)
    end
  end

  def with_env(overrides)
    previous = overrides.keys.to_h { |k| [k, ENV.fetch(k, nil)] }
    overrides.each { |k, v| v.nil? ? ENV.delete(k) : ENV[k] = v }
    yield
  ensure
    previous.each { |k, v| v.nil? ? ENV.delete(k) : ENV[k] = v }
  end
end
