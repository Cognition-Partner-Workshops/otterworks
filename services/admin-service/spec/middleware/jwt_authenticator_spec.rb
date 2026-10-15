require 'rails_helper'

RSpec.describe JwtAuthenticator do
  let(:valid_secret) { 'a-randomly-generated-deployment-secret-0123456789' }
  let(:downstream) { ->(env) { [200, {}, [env['jwt.user_id']]] } }
  let(:middleware) { described_class.new(downstream, secret: valid_secret) }

  def request_with(token)
    Rack::MockRequest.env_for('/api/v1/admin/users', 'HTTP_AUTHORIZATION' => "Bearer #{token}")
  end

  def token_signed_with(secret, sub: 'user-1')
    JWT.encode({ sub: sub, role: 'super_admin', exp: 1.hour.from_now.to_i }, secret, 'HS256')
  end

  describe '.resolve_secret!' do
    it 'raises when no secret is configured' do
      expect { described_class.resolve_secret!(credentials_secret: nil, env_secret: nil, fallback_secret: nil) }
        .to raise_error(JwtAuthenticator::ConfigurationError, /JWT_SECRET environment variable is required/)
    end

    it 'raises when the configured secret is blank' do
      expect { described_class.resolve_secret!(credentials_secret: nil, env_secret: '  ', fallback_secret: nil) }
        .to raise_error(JwtAuthenticator::ConfigurationError, /required/)
    end

    it 'rejects every known default secret' do
      described_class::KNOWN_DEFAULT_SECRETS.each do |known_default|
        expect { described_class.resolve_secret!(credentials_secret: nil, env_secret: known_default) }
          .to raise_error(JwtAuthenticator::ConfigurationError, /publicly known default/)
      end
    end

    it 'prefers Rails credentials, then JWT_SECRET' do
      expect(described_class.resolve_secret!(credentials_secret: 'from-credentials', env_secret: valid_secret))
        .to eq('from-credentials')
      expect(described_class.resolve_secret!(credentials_secret: nil, env_secret: valid_secret)).to eq(valid_secret)
    end

    it 'does not fall back to config/secrets.yml outside the test environment' do
      allow(Rails.env).to receive(:test?).and_return(false)
      expect { described_class.resolve_secret!(credentials_secret: nil, env_secret: nil) }
        .to raise_error(JwtAuthenticator::ConfigurationError)
    end
  end

  describe '#call' do
    it 'authenticates a token signed with the configured secret' do
      status, _headers, body = middleware.call(request_with(token_signed_with(valid_secret)))
      expect(status).to eq(200)
      expect(body).to eq(['user-1'])
    end

    it 'rejects a token forged with a former default secret' do
      forged = token_signed_with('otterworks-local-dev-jwt-secret-change-me-in-production', sub: 'attacker')
      status, = middleware.call(request_with(forged))
      expect(status).to eq(401)
    end
  end
end
