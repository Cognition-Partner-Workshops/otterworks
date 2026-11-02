require 'rails_helper'

RSpec.describe Api::V1::Admin::AlertsController do
  before do
    allow(AdminSettingsService).to receive(:auto_investigate_enabled?).and_return(false)
  end

  let(:rule_labels) do
    { alertname: 'DocumentServiceHighLatency', severity: 'high', affected_service: 'document-service' }
  end
  let(:rule_annotations) do
    { summary: 'P95 latency spike on document-service', description: 'The document-service P95 latency has exceeded 3 seconds.' }
  end

  def ingest(alerts)
    post :ingest, params: { alerts: alerts }, as: :json
    JSON.parse(response.body)
  end

  describe 'POST #ingest' do
    it 'opens an incident for a firing service alert' do
      body = ingest([{ status: 'firing', labels: rule_labels, annotations: rule_annotations }])

      expect(response).to have_http_status(:ok)
      expect(body['processed']).to eq(1)
      incident = Incident.find(body['incidents'].first['incident_id'])
      expect(incident.affected_service).to eq('document-service')
      expect(incident.title).to eq('P95 latency spike on document-service')
      expect(incident.status).to eq('open')
    end

    it 'does not open an incident for a Grafana DatasourceError carrying the rule labels' do
      labels = rule_labels.merge(alertname: 'DatasourceError', rulename: 'DocumentServiceHighLatency')
      annotations = rule_annotations.merge(Error: 'failed to execute query A: Post "http://prometheus:9090/api/v1/query_range": dial tcp: connection refused')

      expect do
        body = ingest([{ status: 'firing', labels: labels, annotations: annotations }])
        expect(body['incidents'].first).to include('skipped' => true, 'reason' => 'datasource_alert', 'alert' => 'DatasourceError')
      end.not_to change(Incident, :count)
    end

    it 'does not open an incident for DatasourceNoData' do
      labels = rule_labels.merge(alertname: 'DatasourceNoData', rulename: 'DocumentServiceHighLatency')

      expect do
        ingest([{ status: 'firing', labels: labels, annotations: rule_annotations }])
      end.not_to change(Incident, :count)
    end

    it 'does not resolve a real incident when a DatasourceError resolves' do
      incident = Incident.create!(
        title: 'P95 latency spike on document-service', description: 'real',
        severity: 'high', status: 'open', affected_service: 'document-service'
      )
      labels = rule_labels.merge(alertname: 'DatasourceError', rulename: 'DocumentServiceHighLatency')

      ingest([{ status: 'resolved', labels: labels, annotations: rule_annotations }])

      expect(incident.reload.status).to eq('open')
    end

    it 'resolves the open incident when the real alert resolves' do
      incident = Incident.create!(
        title: 'P95 latency spike on document-service', description: 'real',
        severity: 'high', status: 'open', affected_service: 'document-service'
      )

      ingest([{ status: 'resolved', labels: rule_labels, annotations: rule_annotations }])

      expect(incident.reload.status).to eq('resolved')
    end
  end
end
