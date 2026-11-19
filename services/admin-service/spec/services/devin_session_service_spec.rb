require 'rails_helper'

RSpec.describe DevinSessionService do
  let(:http) { instance_double(Net::HTTP) }
  before do
    allow(ENV).to receive(:fetch).and_call_original
    allow(ENV).to receive(:fetch).with('DEVIN_API_KEY', nil).and_return('test-key')
    allow(ENV).to receive(:fetch).with('DEVIN_ORG_ID', nil).and_return('test-org')
    allow(Net::HTTP).to receive(:new).and_return(http)
    allow(http).to receive(:use_ssl=)
    allow(http).to receive(:open_timeout=)
    allow(http).to receive(:read_timeout=)
  end

  it 'returns the created session link from the upstream response' do
    response = Net::HTTPCreated.new('1.1', '201', 'Created')
    allow(response).to receive(:body).and_return('{"session_id":"session-1","url":"https://example.test/session"}')
    allow(http).to receive(:request).and_return(response)
    expect(described_class.create_session(incident: build(:incident))).to eq(session_id: 'session-1', url: 'https://example.test/session')
  end

  it 'returns nil for an upstream rejection' do
    response = Net::HTTPServiceUnavailable.new('1.1', '503', 'Unavailable')
    allow(response).to receive(:body).and_return('unavailable')
    allow(http).to receive(:request).and_return(response)
    expect(described_class.create_session(incident: build(:incident))).to be_nil
  end

  it 'returns nil on network timeout' do
    allow(http).to receive(:request).and_raise(Net::ReadTimeout)
    expect(described_class.get_session(session_id: 'session-1')).to be_nil
  end

  it 'returns nil for malformed upstream JSON' do
    response = Net::HTTPOK.new('1.1', '200', 'OK')
    allow(response).to receive(:body).and_return('not-json')
    allow(http).to receive(:request).and_return(response)
    expect(described_class.get_session(session_id: 'session-1')).to be_nil
  end

  it 'does not create a session without API credentials' do
    allow(ENV).to receive(:fetch).with('DEVIN_API_KEY', nil).and_return(nil)
    expect(http).not_to receive(:request)
    expect(described_class.create_session(incident: build(:incident))).to be_nil
  end
end
