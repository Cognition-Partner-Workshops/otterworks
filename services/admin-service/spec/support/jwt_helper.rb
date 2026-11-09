module JwtHelper
  DEFAULT_ROLES = %w[ADMIN USER].freeze

  def jwt_token(user_id: SecureRandom.uuid, email: 'admin@otterworks.com', roles: DEFAULT_ROLES, type: 'access',
                extra_claims: {})
    payload = {
      sub: user_id,
      email: email,
      roles: roles,
      type: type,
      exp: 24.hours.from_now.to_i,
      iat: Time.current.to_i
    }.merge(extra_claims)
    secret = Rails.application.secrets.jwt_secret
    JWT.encode(payload, secret, 'HS256')
  end

  def auth_headers(user_id: SecureRandom.uuid, email: 'admin@otterworks.com', roles: DEFAULT_ROLES, type: 'access',
                   extra_claims: {})
    token = jwt_token(user_id: user_id, email: email, roles: roles, type: type, extra_claims: extra_claims)
    { 'Authorization' => "Bearer #{token}" }
  end

  def set_jwt_env(request, user_id: SecureRandom.uuid, email: 'admin@otterworks.com', roles: DEFAULT_ROLES)
    request.env['jwt.user_id'] = user_id
    request.env['jwt.user_email'] = email
    request.env['jwt.user_roles'] = roles
  end
end

RSpec.configure do |config|
  config.include JwtHelper
end
