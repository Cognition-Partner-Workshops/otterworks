module Api
  module V1
    module Admin
      # Every JWT-authenticated admin controller inherits from here so the
      # role check is enforced in one place. Controllers that are protected
      # by a shared secret instead of a JWT (alerts webhook, chaos) are the
      # only ones that may inherit ApplicationController directly.
      class BaseController < ApplicationController
        ADMIN_ROLES = %w[ADMIN SUPER_ADMIN].freeze

        before_action :require_admin!

        private

        def require_admin!
          return if admin?

          Rails.logger.warn(
            "Admin authorization denied: user=#{current_user_id} roles=#{current_user_roles.inspect} " \
            "path=#{request.path}"
          )
          render json: { error: 'Forbidden: admin role required' }, status: :forbidden
        end

        def admin?
          current_user_roles.intersect?(ADMIN_ROLES)
        end
      end
    end
  end
end
