require 'rails_helper'

RSpec.describe JwtAuthenticator do
  let(:downstream) { ->(_env) { [200, { 'Content-Type' => 'application/json' }, ['{}']] } }
  let(:middleware) { described_class.new(downstream) }

  def call(method, path, headers = {})
    middleware.call(Rack::MockRequest.env_for(path, { method: method }.merge(headers)))
  end

  describe 'chaos endpoint' do
    %w[POST DELETE].each do |method|
      it "rejects #{method} /api/v1/admin/chaos without a JWT, even with X-Chaos-Secret" do
        status, = call(method, '/api/v1/admin/chaos', 'HTTP_X_CHAOS_SECRET' => 'anything')
        expect(status).to eq(401)
      end

      it "rejects #{method} /api/v1/admin/chaos with an invalid JWT" do
        status, = call(method, '/api/v1/admin/chaos', 'HTTP_AUTHORIZATION' => 'Bearer not-a-jwt')
        expect(status).to eq(401)
      end

      it "passes #{method} /api/v1/admin/chaos with a valid JWT" do
        status, = call(method, '/api/v1/admin/chaos', 'HTTP_AUTHORIZATION' => "Bearer #{jwt_token}")
        expect(status).to eq(200)
      end
    end
  end

  it 'keeps the Grafana alert webhook JWT-exempt (guarded by ALERT_WEBHOOK_SECRET instead)' do
    status, = call('POST', '/api/v1/admin/alerts/ingest')
    expect(status).to eq(200)
  end
end
