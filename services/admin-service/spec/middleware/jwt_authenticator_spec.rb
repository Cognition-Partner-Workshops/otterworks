require 'rails_helper'

RSpec.describe JwtAuthenticator do
  let(:downstream) { ->(env) { [200, { 'Content-Type' => 'application/json' }, [env['jwt.user_id'].to_s]] } }
  let(:middleware) { described_class.new(downstream) }

  def call(path, method: 'POST', headers: {})
    env = Rack::MockRequest.env_for(path, method: method)
    headers.each { |k, v| env["HTTP_#{k.upcase.tr('-', '_')}"] = v }
    middleware.call(env)
  end

  it 'skips authentication for the Grafana alert webhook' do
    status, = call('/api/v1/admin/alerts/ingest')
    expect(status).to eq(200)
  end

  it 'rejects regular admin routes without a token' do
    status, = call('/api/v1/admin/users', method: 'GET')
    expect(status).to eq(401)
  end

  describe '/api/v1/admin/chaos' do
    it 'passes through without a token so the controller can verify X-Chaos-Secret' do
      status, _, body = call('/api/v1/admin/chaos')
      expect(status).to eq(200)
      expect(body.first).to eq('')
    end

    it 'authenticates a valid token and exposes the user to the controller' do
      status, _, body = call('/api/v1/admin/chaos', headers: auth_headers(user_id: 'admin-1'))
      expect(status).to eq(200)
      expect(body.first).to eq('admin-1')
    end

    it 'rejects an invalid token instead of falling back to unauthenticated' do
      status, = call('/api/v1/admin/chaos', headers: { 'Authorization' => 'Bearer not-a-jwt' })
      expect(status).to eq(401)
    end
  end
end
