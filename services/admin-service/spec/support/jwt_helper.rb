module JwtHelper
  ADMIN_ROLES = %w[ADMIN USER].freeze

  def jwt_token(user_id: SecureRandom.uuid, email: 'admin@otterworks.com', roles: ADMIN_ROLES)
    payload = {
      sub: user_id,
      email: email,
      roles: roles,
      exp: 24.hours.from_now.to_i,
      iat: Time.current.to_i
    }
    secret = Rails.application.secrets.jwt_secret
    JWT.encode(payload, secret, 'HS256')
  end

  def auth_headers(user_id: SecureRandom.uuid, email: 'admin@otterworks.com', roles: ADMIN_ROLES)
    token = jwt_token(user_id: user_id, email: email, roles: roles)
    { 'Authorization' => "Bearer #{token}" }
  end

  def set_jwt_env(request, user_id: SecureRandom.uuid, email: 'admin@otterworks.com', roles: ADMIN_ROLES)
    request.env['jwt.user_id'] = user_id
    request.env['jwt.user_email'] = email
    request.env['jwt.roles'] = roles
  end
end

RSpec.configure do |config|
  config.include JwtHelper
end
