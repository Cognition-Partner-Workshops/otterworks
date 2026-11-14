class JwtAuthenticator
  class ConfigurationError < StandardError; end

  EXCLUDED_PATHS = %w[/health /metrics /api/v1/admin/alerts/ingest /api/v1/admin/chaos].freeze

  # Signing secrets that have been committed to this repository and must never be used.
  KNOWN_DEFAULT_SECRETS = %w[
    otterworks-local-dev-jwt-secret-change-me-in-production
    dev-jwt-secret-otterworks-2024-change-in-production
    otterworks-dev-secret
    dev_jwt_secret_key
    changeme
    change-me
    secret
  ].freeze

  # Resolves the signing secret once at boot (see config/initializers/jwt_secret.rb).
  # Only the test environment may fall back to the fixture in config/secrets.yml.
  def self.resolve_secret!(credentials_secret: Rails.application.credentials.jwt_secret,
                           env_secret: ENV.fetch('JWT_SECRET', nil),
                           fallback_secret: Rails.env.test? ? Rails.application.secrets.jwt_secret : nil)
    secret = [credentials_secret, env_secret, fallback_secret].find(&:present?)
    raise ConfigurationError, 'JWT_SECRET environment variable is required but not set' if secret.blank?

    if KNOWN_DEFAULT_SECRETS.include?(secret.strip)
      raise ConfigurationError,
            'JWT_SECRET is a publicly known default value; set it to a random secret (e.g. openssl rand -hex 32)'
    end

    secret
  end

  def initialize(app, secret: Rails.application.config.x.jwt_secret)
    @app = app
    @secret = secret.presence || self.class.resolve_secret!
  end

  def call(env)
    request = Rack::Request.new(env)

    return @app.call(env) if skip_authentication?(request)

    token = extract_token(request)
    return unauthorized_response('Missing authorization token') if token.nil?

    payload = decode_token(token)
    return unauthorized_response('Invalid or expired token') if payload.nil?

    env['jwt.payload'] = payload
    env['jwt.user_id'] = payload['sub']
    env['jwt.user_email'] = payload['email']
    env['jwt.user_role'] = payload['role']

    @app.call(env)
  end

  private

  def skip_authentication?(request)
    EXCLUDED_PATHS.any? { |path| request.path == path }
  end

  def extract_token(request)
    header = request.env['HTTP_AUTHORIZATION']
    return nil unless header&.start_with?('Bearer ')

    header.split.last
  end

  def decode_token(token)
    decoded = JWT.decode(token, @secret, true, algorithms: ['HS256', 'HS384'])
    decoded.first
  rescue JWT::DecodeError, JWT::ExpiredSignature, JWT::VerificationError => e
    Rails.logger.warn("JWT authentication failed: #{e.message}")
    nil
  end

  def unauthorized_response(message)
    body = { error: message }.to_json
    [401, { 'Content-Type' => 'application/json' }, [body]]
  end
end
