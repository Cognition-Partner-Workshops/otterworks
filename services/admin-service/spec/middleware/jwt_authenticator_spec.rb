require 'rails_helper'

RSpec.describe JwtAuthenticator do
  let(:app) { ->(env) { [200, {}, [env['jwt.user_email'].to_s]] } }
  let(:middleware) { described_class.new(app) }
  let(:secret) { Rails.application.secrets.jwt_secret }

  def call_with(payload, alg)
    token = JWT.encode(payload.merge(exp: 1.hour.from_now.to_i), secret, alg)
    middleware.call(Rack::MockRequest.env_for('/api/v1/admin/users', 'HTTP_AUTHORIZATION' => "Bearer #{token}"))
  end

  it 'accepts HS512 access tokens issued by auth-service' do
    status, _, body = call_with({ sub: 'u1', email: 'a@b.c', roles: %w[ADMIN USER], type: 'access' }, 'HS512')
    expect(status).to eq(200)
    expect(body.first).to eq('a@b.c')
  end

  it 'forbids access tokens without the ADMIN role' do
    status, = call_with({ sub: 'u1', email: 'a@b.c', roles: %w[USER], type: 'access' }, 'HS512')
    expect(status).to eq(403)
  end

  it 'rejects refresh tokens' do
    status, = call_with({ sub: 'u1', email: 'a@b.c', roles: %w[ADMIN USER], type: 'refresh' }, 'HS512')
    expect(status).to eq(401)
  end

  it 'requires a token for the chaos controls' do
    status, = middleware.call(Rack::MockRequest.env_for('/api/v1/admin/chaos', method: 'POST'))
    expect(status).to eq(401)
  end
end
