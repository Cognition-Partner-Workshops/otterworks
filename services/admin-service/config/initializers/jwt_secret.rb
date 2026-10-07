# Fail fast at boot if the JWT signing secret is missing or a publicly known default.
Rails.application.config.x.jwt_secret = JwtAuthenticator.resolve_secret!
