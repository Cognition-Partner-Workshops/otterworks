require 'rails_helper'

RSpec.describe JwtAuthenticator do
  let(:inner_app) { ->(env) { [200, {}, [env['jwt.user_email'].to_s]] } }
  let(:middleware) { described_class.new(inner_app) }

  def call_with(authorization)
    middleware.call(Rack::MockRequest.env_for('/api/v1/admin/users', 'HTTP_AUTHORIZATION' => authorization))
  end

  it 'passes a request carrying a token signed with the configured secret' do
    status, _headers, body = call_with("Bearer #{jwt_token(email: 'ops@otterworks.com')}")

    expect(status).to eq(200)
    expect(body.first).to eq('ops@otterworks.com')
  end

  it 'rejects a token signed with a different secret' do
    forged = JWT.encode({ sub: 'x', exp: 1.hour.from_now.to_i }, 'not-the-secret', 'HS256')
    status, = call_with("Bearer #{forged}")

    expect(status).to eq(401)
  end
end
