class JwtAuthenticator
  # Unauthenticated paths. /alerts/ingest is a Grafana webhook that cannot carry a
  # JWT; AlertsController verifies its shared secret (fail-closed).
  EXCLUDED_PATHS = %w[/health /metrics /api/v1/admin/alerts/ingest].freeze

  # Paths that accept either a JWT or a controller-verified shared secret
  # (ChaosController, X-Chaos-Secret). A token, when present, is still validated.
  OPTIONAL_AUTH_PATHS = %w[/api/v1/admin/chaos].freeze

  def initialize(app)
    @app = app
  end

  def call(env)
    request = Rack::Request.new(env)

    return @app.call(env) if skip_authentication?(request)

    token = extract_token(request)
    if token.nil?
      return @app.call(env) if optional_authentication?(request)

      return unauthorized_response('Missing authorization token')
    end

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

  def optional_authentication?(request)
    OPTIONAL_AUTH_PATHS.any? { |path| request.path == path }
  end

  def extract_token(request)
    header = request.env['HTTP_AUTHORIZATION']
    return nil unless header&.start_with?('Bearer ')

    header.split.last
  end

  def decode_token(token)
    secret = Rails.application.credentials.jwt_secret || ENV.fetch('JWT_SECRET', Rails.application.secrets.jwt_secret)
    decoded = JWT.decode(token, secret, true, algorithms: ['HS256', 'HS384'])
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
