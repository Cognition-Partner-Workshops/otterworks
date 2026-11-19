require 'rails_helper'

RSpec.describe Api::V1::Admin::AlertsController do
  let(:alert) do
    { status: 'firing', labels: { alertname: 'Alert B', severity: 'warning', affected_service: 'search-service' },
      annotations: { summary: 'Search errors', description: 'Requests failed', runbook_url: 'https://example.test/runbook' } }
  end
  before do
    allow(ENV).to receive(:fetch).and_call_original
    allow(ENV).to receive(:fetch).with('ALERT_WEBHOOK_SECRET', nil).and_return('webhook-secret')
    request.headers['X-Alert-Secret'] = 'webhook-secret'
    allow(AdminSettingsService).to receive(:auto_investigate_enabled?).and_return(false)
    allow(DevinSessionService).to receive(:create_session).and_return(session_id: 'session-1', url: 'https://example.test/session')
  end

  it 'rejects the wrong webhook secret without creating incidents' do
    request.headers['X-Alert-Secret'] = 'wrong'
    expect { post :ingest, params: { alerts: [alert] } }.not_to change(Incident, :count)
    expect(response).to have_http_status(:unauthorized)
    expect(JSON.parse(response.body)).to eq('error' => 'Unauthorized')
  end

  it 'accepts the Bearer webhook secret and an empty batch' do
    request.headers['X-Alert-Secret'] = nil
    request.headers['Authorization'] = 'Bearer webhook-secret'
    post :ingest, params: { alerts: [] }, as: :json
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)).to include('received' => 0, 'processed' => 0)
  end

  { 'critical' => 'critical', 'high' => 'high', 'warning' => 'medium', 'info' => 'low', 'unknown' => 'medium' }.each do |input, severity|
    it "maps #{input} severity on a firing alert" do
      alert[:labels][:severity] = input
      post :ingest, params: { alerts: [alert] }
      expect(response).to have_http_status(:ok)
      expect(Incident.last).to have_attributes(severity: severity, status: 'open', title: 'Search errors')
      expect(Incident.last.description).to include('Alert B', 'https://example.test/runbook')
      expect(Incident.last.devin_session_id).to be_nil
    end
  end

  it 'honors enabled auto-investigation and stores the session' do
    allow(AdminSettingsService).to receive(:auto_investigate_enabled?).and_return(true)
    post :ingest, params: { alerts: [alert] }
    expect(Incident.last).to have_attributes(status: 'investigating', devin_session_id: 'session-1')
    expect(JSON.parse(response.body)['incidents'].first['devin_session']).to be true
  end

  it 'does not call Devin when auto-investigation is disabled' do
    expect(DevinSessionService).not_to receive(:create_session)
    post :ingest, params: { alerts: [alert] }
    expect(Incident.last.status).to eq('open')
  end

  it 'deduplicates firing alerts per service' do
    existing = create(:incident)
    expect { post :ingest, params: { alerts: [alert] } }.not_to change(Incident, :count)
    expect(JSON.parse(response.body)['incidents']).to eq([{ 'skipped' => true, 'incident_id' => existing.id, 'reason' => 'duplicate' }])
  end

  it 'resolves the incident opened by the firing alert' do
    post :ingest, params: { alerts: [alert] }
    incident = Incident.last
    post :ingest, params: { alerts: [alert.merge(status: 'resolved')] }
    expect(response).to have_http_status(:ok)
    expect(incident.reload.status).to eq('resolved')
    expect(incident.resolved_at).to be_present
  end

  it 'resolved alert for alert A does not resolve the incident opened by alert B on the same service' do
    post :ingest, params: { alerts: [alert] }
    incident = Incident.last
    other = alert.deep_dup
    other[:status] = 'resolved'
    other[:labels][:alertname] = 'Alert A'
    pending 'BUG: app/controllers/api/v1/admin/alerts_controller.rb:105-114 resolves by service while ignoring alert_name'
    post :ingest, params: { alerts: [other] }
    expect(incident.reload.status).to eq('open')
  end

  it 'rejects a malformed alerts collection' do
    post :ingest, params: { alerts: 'invalid' }
    expect(response).to have_http_status(:bad_request)
    expect(JSON.parse(response.body)).to eq('error' => 'Missing alerts array')
  end

  it 'ignores alerts without a service or with an unknown status' do
    alert[:labels].delete(:affected_service)
    post :ingest, params: { alerts: [alert, alert.merge(status: 'unknown')] }
    expect(JSON.parse(response.body)).to include('processed' => 0)
    expect(Incident.count).to eq(0)
  end
end
