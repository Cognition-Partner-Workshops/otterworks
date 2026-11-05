require 'spec_helper'
require_relative '../../app/services/chaos_probe_service'

RSpec.describe ChaosProbeService do
  it 'signs the file and search probes with short-lived access identities' do
    secret = 'unit-test-chaos-signing-key-not-a-deployment-secret'
    allow(ENV).to receive(:fetch).with('JWT_SECRET').and_return(secret)
    http = instance_double(Net::HTTP, open_timeout: nil, read_timeout: nil)
    allow(http).to receive(:open_timeout=)
    allow(http).to receive(:read_timeout=)
    allow(Net::HTTP).to receive(:new).and_return(http)

    %w[file-service search-service].each do |service|
      expect(http).to receive(:request) do |request|
        token = request['Authorization'].delete_prefix('Bearer ')
        claims, = JWT.decode(token, secret, true, algorithm: 'HS256')
        expect(claims['sub']).to eq(described_class::PROBE_USER_ID)
        expect(claims['type']).to eq('access')
        expect(claims['exp']).to be_between(Time.now.to_i, Time.now.to_i + 60)
      end
      described_class.fire_probe(described_class::SERVICE_PROBES.fetch(service))
    end
  end
end
