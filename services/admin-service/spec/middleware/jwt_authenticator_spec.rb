require 'rails_helper'

RSpec.describe JwtAuthenticator do
  let(:downstream) { ->(env) { [200, { 'Content-Type' => 'application/json' }, [env.slice(*env.keys.grep(/^jwt\./)).to_json]] } }
  let(:middleware) { described_class.new(downstream) }

  def call(path: '/api/v1/admin/users', headers: {})
    env = Rack::MockRequest.env_for(path)
    headers.each { |key, value| env["HTTP_#{key.upcase.tr('-', '_')}"] = value }
    middleware.call(env)
  end

  it 'exposes the roles array from the token as jwt.user_roles' do
    status, _, body = call(headers: auth_headers(roles: %w[Admin user]))
    expect(status).to eq(200)
    expect(JSON.parse(body.first)['jwt.user_roles']).to eq(%w[ADMIN USER])
  end

  it 'yields an empty role list when the token has no roles claim' do
    status, _, body = call(headers: auth_headers(roles: nil))
    expect(status).to eq(200)
    expect(JSON.parse(body.first)['jwt.user_roles']).to eq([])
  end

  it 'rejects refresh tokens' do
    status, = call(headers: auth_headers(type: 'refresh'))
    expect(status).to eq(401)
  end

  it 'rejects tokens signed with another secret' do
    forged = JWT.encode({ sub: 'x', roles: %w[ADMIN], type: 'access' }, 'not-the-secret', 'HS256')
    status, = call(headers: { 'Authorization' => "Bearer #{forged}" })
    expect(status).to eq(401)
  end

  context 'when an issuer and audience are pinned' do
    around do |example|
      previous = ENV.slice('JWT_ISSUER', 'JWT_AUDIENCE')
      ENV['JWT_ISSUER'] = 'otterworks-auth'
      ENV['JWT_AUDIENCE'] = 'otterworks-admin'
      example.run
    ensure
      ENV.delete('JWT_ISSUER')
      ENV.delete('JWT_AUDIENCE')
      ENV.update(previous)
    end

    it 'accepts tokens with the expected iss and aud' do
      headers = auth_headers(extra_claims: { iss: 'otterworks-auth', aud: 'otterworks-admin' })
      status, = call(headers: headers)
      expect(status).to eq(200)
    end

    it 'rejects tokens from another issuer' do
      headers = auth_headers(extra_claims: { iss: 'someone-else', aud: 'otterworks-admin' })
      status, = call(headers: headers)
      expect(status).to eq(401)
    end

    it 'rejects tokens for another audience' do
      headers = auth_headers(extra_claims: { iss: 'otterworks-auth', aud: 'file-service' })
      status, = call(headers: headers)
      expect(status).to eq(401)
    end
  end
end
