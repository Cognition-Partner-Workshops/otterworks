require 'rails_helper'

RSpec.describe Api::V1::Admin::IncidentsController do
  let(:actor_id) { SecureRandom.uuid }
  let(:session_result) { { session_id: 'session-1', url: 'https://example.test/session-1' } }
  before do
    set_jwt_env(request, user_id: actor_id)
    allow(DevinSessionService).to receive(:create_session).and_return(session_result)
    allow(DevinSessionService).to receive(:get_session).and_return(nil)
  end

  it 'creates an investigating incident, session and audit entry' do
    post :create, params: { incident: attributes_for(:incident) }
    expect(response).to have_http_status(:created)
    incident = Incident.find(JSON.parse(response.body)['id'])
    expect(incident).to have_attributes(status: 'investigating', reporter_id: actor_id, devin_session_id: 'session-1')
    expect(AuditLog.last).to have_attributes(action: 'incident.created', resource_id: incident.id, actor_id: actor_id)
  end

  it 'returns validation details without creating an invalid incident' do
    expect { post :create, params: { incident: { title: 'Only title' } } }.not_to change(Incident, :count)
    expect(response).to have_http_status(:unprocessable_entity)
    expect(JSON.parse(response.body)['details']).to include("Description can't be blank")
  end

  it 'lists only matching active incidents with pagination' do
    create(:incident, severity: 'low')
    create(:incident, status: 'resolved')
    matches = create_list(:incident, 2)
    get :index, params: { severity: 'high', status: 'open', active: 'true', per_page: 1, page: 2 }
    body = JSON.parse(response.body)
    expect(response).to have_http_status(:ok)
    expect(body).to include('total' => 2, 'page' => 2, 'per_page' => 1)
    expect(body['incidents'].map { |i| i['id'] }).to eq([matches.first.id])
  end

  it 'returns an empty incident list' do
    get :index
    expect(JSON.parse(response.body)).to include('incidents' => [], 'total' => 0)
  end

  it 'refreshes an active session when showing an incident' do
    incident = create(:incident, devin_session_id: 'session-1')
    allow(DevinSessionService).to receive(:get_session).with(session_id: 'session-1').and_return(status: 'finished', url: nil)
    get :show, params: { id: incident.id }
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)['devin_session_status']).to eq('finished')
    expect(incident.reload.devin_session_status).to eq('finished')
  end

  it 'rejects invalid status transitions without changing the incident' do
    incident = create(:incident)
    put :update, params: { id: incident.id, incident: { status: 'closed' } }
    expect(response).to have_http_status(:unprocessable_entity)
    expect(JSON.parse(response.body)['error']).to eq('Invalid status transition')
    expect(incident.reload.status).to eq('open')
  end

  it 'resolves and closes with timestamps and audit entries' do
    incident = create(:incident)
    put :update, params: { id: incident.id, incident: { status: 'resolved' } }
    expect(response).to have_http_status(:ok)
    expect(incident.reload.resolved_at).to be_within(5.seconds).of(Time.current)
    put :update, params: { id: incident.id, incident: { status: 'closed' } }
    expect(response).to have_http_status(:ok)
    expect(incident.reload.closed_at).to be_within(5.seconds).of(Time.current)
    expect(AuditLog.where(resource_id: incident.id).pluck(:action)).to contain_exactly('incident.resolved', 'incident.closed')
  end

  it 'moves an open incident into investigation' do
    incident = create(:incident)
    put :update, params: { id: incident.id, incident: { status: 'investigating' } }
    expect(response).to have_http_status(:ok)
    expect(incident.reload.status).to eq('investigating')
  end

  it 'blocks deletion with an active session' do
    incident = create(:incident, devin_session_id: 'session-1', devin_session_status: 'running')
    expect { delete :destroy, params: { id: incident.id } }.not_to change(Incident, :count)
    expect(response).to have_http_status(:conflict)
    expect(JSON.parse(response.body)['error']).to eq('Cannot delete incident with an active Devin session')
  end

  it 'deletes an incident without an active session and audits it' do
    incident = create(:incident)
    expect { delete :destroy, params: { id: incident.id } }.to change(Incident, :count).by(-1)
    expect(response).to have_http_status(:no_content)
    expect(AuditLog.last.action).to eq('incident.deleted')
  end

  it 'triggers a session and persists its link' do
    incident = create(:incident)
    post :trigger_session, params: { id: incident.id }
    expect(response).to have_http_status(:ok)
    expect(incident.reload).to have_attributes(devin_session_id: 'session-1', devin_session_url: session_result[:url], devin_session_status: 'running')
  end

  it 'rejects duplicate session creation' do
    incident = create(:incident, devin_session_id: 'existing')
    post :trigger_session, params: { id: incident.id }
    expect(response).to have_http_status(:unprocessable_entity)
    expect(JSON.parse(response.body)['error']).to eq('Incident already has a Devin session')
  end

  it 'reports upstream session failure without recording a session' do
    incident = create(:incident)
    allow(DevinSessionService).to receive(:create_session).and_return(nil)
    post :trigger_session, params: { id: incident.id }
    expect(response).to have_http_status(:service_unavailable)
    expect(JSON.parse(response.body)['error']).to eq('Failed to create Devin session')
    expect(incident.reload.devin_session_id).to be_nil
  end
end
