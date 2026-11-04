module JwtHelper
  ADMIN_TOKEN_ROLES = %w[USER OWNER].freeze

  def jwt_token(user_id: SecureRandom.uuid, email: 'admin@otterworks.com', roles: ADMIN_TOKEN_ROLES)
    payload = {
      sub: user_id,
      email: email,
      roles: roles,
      type: 'access',
      exp: 24.hours.from_now.to_i,
      iat: Time.current.to_i
    }
    secret = Rails.application.secrets.jwt_secret
    JWT.encode(payload, secret, 'HS256')
  end

  def auth_headers(user_id: SecureRandom.uuid, email: 'admin@otterworks.com', roles: ADMIN_TOKEN_ROLES)
    token = jwt_token(user_id: user_id, email: email, roles: roles)
    { 'Authorization' => "Bearer #{token}" }
  end

  def set_jwt_env(request, user_id: SecureRandom.uuid, email: 'admin@otterworks.com', roles: ADMIN_TOKEN_ROLES)
    request.env['jwt.user_id'] = user_id
    request.env['jwt.user_email'] = email
    request.env['jwt.user_roles'] = roles
  end
end

RSpec.configure do |config|
  config.include JwtHelper
end
