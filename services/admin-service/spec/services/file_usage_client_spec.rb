require 'rails_helper'

RSpec.describe FileUsageClient do
  let(:http) { instance_double(Net::HTTP) }

  before do
    allow(ENV).to receive(:fetch).and_call_original
    allow(ENV).to receive(:fetch).with('FILE_SERVICE_URL', 'http://file-service:8082')
                                 .and_return('http://file-service:8082')
    allow(Net::HTTP).to receive(:new).with('file-service', 8082).and_return(http)
    allow(http).to receive(:use_ssl=)
    allow(http).to receive(:open_timeout=)
    allow(http).to receive(:read_timeout=)
  end

  it 'posts owner ids to the internal usage endpoint and parses the response' do
    response = instance_double(Net::HTTPOK, code: '200', body: {
      file_count: 1,
      total_bytes: 123,
      owners: [{ owner_id: 'owner-1', file_count: 1, total_bytes: 123 }]
    }.to_json)
    expect(http).to receive(:request) do |request|
      expect(request.method).to eq('POST')
      expect(request.path).to eq('/internal/usage')
      expect(request['Content-Type']).to eq('application/json')
      expect(JSON.parse(request.body)).to eq('owner_ids' => ['owner-1'])
      response
    end

    expect(described_class.usage(['owner-1'])).to eq(
      file_count: 1,
      total_bytes: 123,
      owners: [{ owner_id: 'owner-1', file_count: 1, total_bytes: 123 }]
    )
    expect(http).to have_received(:open_timeout=).with(2)
    expect(http).to have_received(:read_timeout=).with(5)
  end

  it 'batches requests into groups of at most 100 owners' do
    owner_ids = 101.times.map(&:to_s)
    expect(http).to receive(:request).twice do |request|
      requested_ids = JSON.parse(request.body).fetch('owner_ids')
      double(code: '200', body: {
        file_count: requested_ids.length,
        total_bytes: requested_ids.length * 10,
        owners: requested_ids.map do |owner_id|
          { owner_id: owner_id, file_count: 1, total_bytes: 10 }
        end
      }.to_json)
    end

    usage = described_class.usage(owner_ids)

    expect(usage[:file_count]).to eq(101)
    expect(usage[:total_bytes]).to eq(1010)
    expect(usage[:owners].map { |owner| owner[:owner_id] }).to eq(owner_ids)
  end

  it 'raises an error for a non-success response' do
    allow(http).to receive(:request).and_return(double(code: '500', body: 'unavailable'))

    expect { described_class.usage(['owner-1']) }
      .to raise_error(FileUsageClient::Error, 'file service returned HTTP 500')
  end

  it 'raises an error for a timeout' do
    allow(http).to receive(:request).and_raise(Net::ReadTimeout)

    expect { described_class.usage(['owner-1']) }.to raise_error(FileUsageClient::Error)
  end

  it 'raises an error for invalid JSON' do
    allow(http).to receive(:request).and_return(double(code: '200', body: '{'))

    expect { described_class.usage(['owner-1']) }.to raise_error(FileUsageClient::Error)
  end
end
