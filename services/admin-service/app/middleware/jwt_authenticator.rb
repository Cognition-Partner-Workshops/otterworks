class JwtAuthenticator
  EXCLUDED_PATHS = %w[/health /metrics /api/v1/admin/alerts/ingest /api/v1/admin/chaos].freeze
  ACCESS_TOKEN_TYPE = 'access'.freeze

  def initialize(app)
    @app = app
  end

  def call(env)
    request = Rack::Request.new(env)

    return @app.call(env) if skip_authentication?(request)

    token = extract_token(request)
    return unauthorized_response('Missing authorization token') if token.nil?

    payload = decode_token(token)
    return unauthorized_response('Invalid or expired token') if payload.nil?
    return unauthorized_response('Token is not an access token') unless access_token?(payload)

    env['jwt.payload'] = payload
    env['jwt.user_id'] = payload['sub']
    env['jwt.user_email'] = payload['email']
    env['jwt.user_roles'] = extract_roles(payload)

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
    secret = Rails.application.credentials.jwt_secret || ENV.fetch('JWT_SECRET', Rails.application.secrets.jwt_secret)
    decoded = JWT.decode(token, secret, true, decode_options)
    decoded.first
  rescue JWT::DecodeError, JWT::ExpiredSignature, JWT::VerificationError => e
    Rails.logger.warn("JWT authentication failed: #{e.message}")
    nil
  end

  # Issuer/audience are pinned whenever the deployment configures them
  # (JWT_ISSUER / JWT_AUDIENCE); auth-service does not emit iss/aud today,
  # so they are optional rather than mandatory.
  def decode_options
    options = { algorithms: %w[HS256 HS384] }
    expected_issuer = ENV.fetch('JWT_ISSUER', nil).presence
    expected_audience = ENV.fetch('JWT_AUDIENCE', nil).presence
    options.merge!(iss: expected_issuer, verify_iss: true) if expected_issuer
    options.merge!(aud: expected_audience, verify_aud: true) if expected_audience
    options
  end

  # auth-service stamps `type: access` on access tokens and `type: refresh`
  # on refresh tokens; only the former may call the admin API.
  def access_token?(payload)
    payload['type'] == ACCESS_TOKEN_TYPE
  end

  # auth-service issues roles as a `roles` array (e.g. ["ADMIN", "USER"]).
  def extract_roles(payload)
    Array(payload['roles']).map { |role| role.to_s.upcase }.reject(&:empty?)
  end

  def unauthorized_response(message)
    body = { error: message }.to_json
    [401, { 'Content-Type' => 'application/json' }, [body]]
  end
end
