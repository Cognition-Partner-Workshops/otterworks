require 'rails_helper'

RSpec.describe Api::V1::Admin::AlertsController do
  describe 'POST #ingest' do
    it 'fails closed when ALERT_WEBHOOK_SECRET is not configured' do
      with_env('ALERT_WEBHOOK_SECRET' => nil) do
        post :ingest, params: { alerts: [] }, as: :json
      end
      expect(response).to have_http_status(:unauthorized)
    end

    it 'fails closed when ALERT_WEBHOOK_SECRET is empty' do
      with_env('ALERT_WEBHOOK_SECRET' => '') do
        request.headers['X-Alert-Secret'] = ''
        post :ingest, params: { alerts: [] }, as: :json
      end
      expect(response).to have_http_status(:unauthorized)
    end

    it 'rejects a missing secret' do
      with_env('ALERT_WEBHOOK_SECRET' => 'hook-secret') do
        post :ingest, params: { alerts: [] }, as: :json
      end
      expect(response).to have_http_status(:unauthorized)
    end

    it 'rejects a wrong secret' do
      with_env('ALERT_WEBHOOK_SECRET' => 'hook-secret') do
        request.headers['X-Alert-Secret'] = 'nope'
        post :ingest, params: { alerts: [] }, as: :json
      end
      expect(response).to have_http_status(:unauthorized)
    end

    it 'accepts the secret via X-Alert-Secret' do
      with_env('ALERT_WEBHOOK_SECRET' => 'hook-secret') do
        request.headers['X-Alert-Secret'] = 'hook-secret'
        post :ingest, params: { alerts: [] }, as: :json
      end
      expect(response).to have_http_status(:ok)
    end

    it 'accepts the secret via Authorization: Bearer (Grafana contact point)' do
      with_env('ALERT_WEBHOOK_SECRET' => 'hook-secret') do
        request.headers['Authorization'] = 'Bearer hook-secret'
        post :ingest, params: { alerts: [] }, as: :json
      end
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
