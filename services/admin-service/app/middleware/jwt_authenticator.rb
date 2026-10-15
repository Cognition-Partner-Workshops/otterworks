class JwtAuthenticator
  EXCLUDED_PATHS = %w[/health /metrics /api/v1/admin/alerts/ingest /api/v1/admin/chaos].freeze
  # admin-service tokens carry a singular `role`; auth-service tokens carry `roles` (e.g. ["ADMIN", "USER"]).
  ADMIN_ROLES = %w[admin super_admin].freeze

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
    return forbidden_response unless admin?(payload)

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
    secret = Rails.application.credentials.jwt_secret || ENV.fetch('JWT_SECRET', Rails.application.secrets.jwt_secret)
    decoded = JWT.decode(token, secret, true, algorithms: ['HS256', 'HS384'])
    decoded.first
  rescue JWT::DecodeError, JWT::ExpiredSignature, JWT::VerificationError => e
    Rails.logger.warn("JWT authentication failed: #{e.message}")
    nil
  end

  def admin?(payload)
    roles = [payload['role'], *Array(payload['roles'])].compact.map { |role| role.to_s.downcase }
    roles.intersect?(ADMIN_ROLES)
  end

  def forbidden_response
    [403, { 'Content-Type' => 'application/json' }, [{ error: 'Admin role required' }.to_json]]
  end

  def unauthorized_response(message)
    body = { error: message }.to_json
    [401, { 'Content-Type' => 'application/json' }, [body]]
  end
end
