module Api
  module V1
    module Admin
      class FinanceController < ApplicationController
        before_action :require_finance_admin

        def dashboard
          render json: FinanceWarehouse::DashboardQueries.new.dashboard
        rescue FinanceWarehouse::DashboardQueries::Disabled
          render json: { error: 'finance warehouse is disabled' }, status: :not_found
        rescue FinanceWarehouse::SnowflakeClient::Unavailable
          render json: { error: 'finance warehouse unavailable' }, status: :service_unavailable
        end

        private

        def require_finance_admin
          unless current_user_id.is_a?(String) && current_user_id.present?
            return render json: { error: 'Authenticated subject required' }, status: :unauthorized
          end

          return if finance_admin?

          render json: { error: 'Administrator role required' }, status: :forbidden
        end

        def finance_admin?
          roles = [current_user_role]
          payload = request.env['jwt.payload']
          roles += payload['roles'] if payload.is_a?(Hash) && payload['roles'].is_a?(Array)
          roles.any? { |role| role.is_a?(String) && %w[super_admin admin].include?(role.downcase) }
        end
      end
    end
  end
end
