require 'rails_helper'

RSpec.describe Api::V1::Admin::IncidentsController do
  before { set_jwt_env(request) }

  let(:incident) do
    Incident.create!(title: 'File uploads failing', description: 'alert', severity: 'critical',
                     status: 'open', affected_service: 'file-service')
  end
  let(:link) { { session_id: 'abc123', url: 'https://app.devin.ai/sessions/abc123' } }

  describe 'PATCH #link_session' do
    it 'attaches the session and moves the incident to investigating' do
      patch :link_session, params: { id: incident.id, devin_session: link }
      expect(response).to have_http_status(:ok)
      incident.reload
      expect(incident.devin_session_url).to eq(link[:url])
      expect(incident.devin_session_status).to eq('running')
      expect(incident.status).to eq('investigating')
    end

    it 'rejects a non-https url' do
      patch :link_session, params: { id: incident.id, devin_session: link.merge(url: 'javascript:alert(1)') }
      expect(response).to have_http_status(:unprocessable_entity)
      expect(incident.reload.devin_session_id).to be_nil
    end

    it 'does not overwrite an existing session' do
      incident.update!(devin_session_id: 'first', devin_session_url: 'https://app.devin.ai/sessions/first')
      patch :link_session, params: { id: incident.id, devin_session: link }
      expect(response).to have_http_status(:unprocessable_entity)
      expect(incident.reload.devin_session_id).to eq('first')
    end
  end
end
