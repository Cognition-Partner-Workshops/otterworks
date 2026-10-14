require 'rails_helper'

RSpec.describe JwtAuthenticator do
  let(:downstream) { ->(env) { [200, { 'Content-Type' => 'application/json' }, [env.slice('jwt.user_id', 'jwt.user_email', 'jwt.user_role').to_json]] } }
  let(:middleware) { described_class.new(downstream) }
  let(:mock) { Rack::MockRequest.new(middleware) }
  let(:secret) { Rails.application.credentials.jwt_secret || ENV.fetch('JWT_SECRET', Rails.application.secrets.jwt_secret) }

  def token(payload = {}, key: secret, alg: 'HS256')
    JWT.encode({ sub: 'user-1', email: 'qa@otterworks.io', role: 'admin', exp: 1.hour.from_now.to_i }.merge(payload), key, alg)
  end

  def get(path, auth = nil)
    mock.get(path, 'HTTP_AUTHORIZATION' => auth)
  end

  %w[/health /metrics /api/v1/admin/alerts/ingest /api/v1/admin/chaos].each do |path|
    it "lets #{path} through without a token" do
      expect(get(path).status).to eq(200)
    end
  end

  it 'requires a token for nested paths under excluded prefixes' do
    expect(get('/health/services').status).to eq(401)
  end

  it 'rejects a missing Authorization header' do
    res = get('/api/v1/admin/users')
    expect(res.status).to eq(401)
    expect(JSON.parse(res.body)['error']).to eq('Missing authorization token')
  end

  it 'rejects a non-Bearer scheme' do
    expect(get('/api/v1/admin/users', "Basic #{token}").status).to eq(401)
  end

  it 'rejects a token signed with the wrong secret' do
    res = get('/api/v1/admin/users', "Bearer #{token({}, key: 'not-the-secret')}")
    expect(res.status).to eq(401)
    expect(JSON.parse(res.body)['error']).to eq('Invalid or expired token')
  end

  it 'rejects an expired token' do
    expect(get('/api/v1/admin/users', "Bearer #{token({ exp: 1.minute.ago.to_i })}").status).to eq(401)
  end

  it 'rejects an unsigned (alg=none) token' do
    unsigned = JWT.encode({ sub: 'attacker', role: 'super_admin' }, nil, 'none')
    expect(get('/api/v1/admin/users', "Bearer #{unsigned}").status).to eq(401)
  end

  it 'rejects garbage tokens' do
    expect(get('/api/v1/admin/users', 'Bearer not.a.jwt').status).to eq(401)
  end

  it 'accepts a valid HS256 token and exposes claims to the app' do
    res = get('/api/v1/admin/users', "Bearer #{token}")
    expect(res.status).to eq(200)
    expect(JSON.parse(res.body)).to eq('jwt.user_id' => 'user-1', 'jwt.user_email' => 'qa@otterworks.io',
                                       'jwt.user_role' => 'admin')
  end

  it 'accepts a valid HS384 token' do
    expect(get('/api/v1/admin/users', "Bearer #{token({}, alg: 'HS384')}").status).to eq(200)
  end

  it 'returns JSON content type on 401' do
    expect(get('/api/v1/admin/users').headers['Content-Type']).to eq('application/json')
  end
end
