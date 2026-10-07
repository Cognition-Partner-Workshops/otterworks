require 'rails_helper'

RSpec.describe Api::V1::Admin::AlertsController do
  let(:secret) { 'test-alert-webhook-secret' }
  let(:payload) do
    {
      alerts: [{
        status: 'firing',
        labels: { alertname: 'HighErrorRate', affected_service: 'search-service', severity: 'critical' },
        annotations: { summary: 'search-service 5xx rate above threshold' }
      }]
    }
  end

  around do |example|
    original = ENV.fetch('ALERT_WEBHOOK_SECRET', nil)
    example.run
  ensure
    ENV['ALERT_WEBHOOK_SECRET'] = original
  end

  before do
    allow(AdminSettingsService).to receive(:auto_investigate_enabled?).and_return(true)
    allow(DevinSessionService).to receive(:create_session).and_return(nil)
  end

  def ingest(headers = {})
    request.headers.merge!(headers)
    post :ingest, params: payload, as: :json
  end

  shared_examples 'a rejected alert' do |status|
    it "responds #{status} without creating incidents or Devin sessions" do
      expect { ingest(headers) }.not_to change(Incident, :count)
      expect(response).to have_http_status(status)
      expect(DevinSessionService).not_to have_received(:create_session)
    end
  end

  describe 'POST #ingest' do
    context 'when ALERT_WEBHOOK_SECRET is unset' do
      before { ENV.delete('ALERT_WEBHOOK_SECRET') }

      it_behaves_like 'a rejected alert', :service_unavailable do
        let(:headers) { {} }
      end

      it_behaves_like 'a rejected alert', :service_unavailable do
        let(:headers) { { 'Authorization' => 'Bearer ' } }
      end
    end

    context 'when ALERT_WEBHOOK_SECRET is empty' do
      before { ENV['ALERT_WEBHOOK_SECRET'] = '' }

      it_behaves_like 'a rejected alert', :service_unavailable do
        let(:headers) { { 'X-Alert-Secret' => '' } }
      end
    end

    context 'when ALERT_WEBHOOK_SECRET is configured' do
      before { ENV['ALERT_WEBHOOK_SECRET'] = secret }

      context 'without a secret' do
        it_behaves_like 'a rejected alert', :unauthorized do
          let(:headers) { {} }
        end
      end

      context 'with a wrong X-Alert-Secret' do
        it_behaves_like 'a rejected alert', :unauthorized do
          let(:headers) { { 'X-Alert-Secret' => 'wrong-secret' } }
        end
      end

      context 'with a wrong Bearer token' do
        it_behaves_like 'a rejected alert', :unauthorized do
          let(:headers) { { 'Authorization' => 'Bearer wrong-secret' } }
        end
      end

      it 'accepts the correct X-Alert-Secret and creates an incident' do
        expect { ingest('X-Alert-Secret' => secret) }.to change(Incident, :count).by(1)
        expect(response).to have_http_status(:ok)
        expect(response.parsed_body).to include('received' => 1, 'processed' => 1)
        expect(Incident.last).to have_attributes(affected_service: 'search-service', severity: 'critical')
        expect(DevinSessionService).to have_received(:create_session).once
      end

      it 'accepts the correct Bearer token sent by the Grafana contact point' do
        expect { ingest('Authorization' => "Bearer #{secret}") }.to change(Incident, :count).by(1)
        expect(response).to have_http_status(:ok)
      end
    end
  end
end
