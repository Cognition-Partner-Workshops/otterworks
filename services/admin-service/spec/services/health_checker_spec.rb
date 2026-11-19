require 'rails_helper'

RSpec.describe HealthChecker do
  describe '.check_all' do
    before do
      allow(described_class).to receive(:check_service) do |name|
        described_class::ServiceStatus.new(name: name, status: 'healthy', latency_ms: 1)
      end
      allow(described_class).to receive(:check_database).and_return(status: 'healthy')
      allow(described_class).to receive(:check_redis).and_return(status: 'healthy')
    end

    it 'reports healthy when all dependencies are healthy' do
      result = described_class.check_all
      expect(result[:status]).to eq('healthy')
      expect(result[:services].map { |s| s[:name] }).to eq(described_class::SERVICES)
    end

    it 'reports degraded when a service is unhealthy' do
      allow(described_class).to receive(:check_service).with('auth-service').and_return(described_class::ServiceStatus.new(name: 'auth-service', status: 'unhealthy'))
      expect(described_class.check_all[:status]).to eq('degraded')
    end

    %i[database redis].each do |dependency|
      it "does not report healthy when #{dependency} is down" do
        allow(described_class).to receive("check_#{dependency}").and_return(status: 'unhealthy')
        pending 'BUG: app/services/health_checker.rb:16-24 overall health excludes database and Redis failures'
        expect(described_class.check_all[:status]).not_to eq('healthy')
      end
    end
  end

  describe '.check_service' do
    let(:http) { instance_double(Net::HTTP) }
    before do
      allow(Net::HTTP).to receive(:new).and_return(http)
      allow(http).to receive(:open_timeout=)
      allow(http).to receive(:read_timeout=)
    end

    it 'reports healthy for HTTP 200' do
      allow(http).to receive(:get).with('/health').and_return(double(code: '200'))
      expect(described_class.check_service('auth-service').status).to eq('healthy')
    end

    it 'reports unhealthy for a non-success health response' do
      allow(http).to receive(:get).and_return(double(code: '503'))
      expect(described_class.check_service('auth-service').status).to eq('unhealthy')
    end

    [Net::ReadTimeout, Errno::ECONNREFUSED].each do |error|
      it "reports #{error} as unhealthy without raising" do
        allow(http).to receive(:get).and_raise(error)
        result = described_class.check_service('auth-service')
        expect(result.status).to eq('unhealthy')
        expect(result.message).to be_present
      end
    end
  end

  it 'reports database query errors as unhealthy' do
    allow(ActiveRecord::Base.connection).to receive(:execute).with('SELECT 1').and_raise(ActiveRecord::ConnectionNotEstablished, 'offline')
    expect(described_class.check_database).to include(status: 'unhealthy', message: 'offline')
  end

  it 'reports Redis connection errors as unhealthy' do
    redis = instance_double(Redis, close: nil)
    allow(Redis).to receive(:new).and_return(redis)
    allow(redis).to receive(:ping).and_raise(Redis::BaseError, 'offline')
    expect(described_class.check_redis).to include(status: 'unhealthy', message: 'offline')
  end
end
