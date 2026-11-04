module Api
  module V1
    module Admin
      class BulkController < ApplicationController
        # POST /api/v1/admin/bulk/users
        def users
          operation = params.require(:operation)
          user_ids = params.require(:user_ids)

          unless user_ids.is_a?(Array) && user_ids.any?
            return render json: { error: 'user_ids must be a non-empty array' }, status: :bad_request
          end

          if operation == 'update_role'
            denial = bulk_role_change_denial(user_ids, bulk_params[:role])
            return render json: { error: denial }, status: :forbidden if denial
          end

          result = BulkOperationsService.process(
            operation: operation,
            user_ids: user_ids,
            params: bulk_params,
            request: request
          )

          render json: {
            operation: operation,
            success_count: result.success_count,
            failure_count: result.failure_count,
            errors: result.errors
          }, status: bulk_status(result)
        end

        private

        def bulk_role_change_denial(user_ids, new_role)
          return 'Only an owner or super_admin may change roles' if caller_role_rank.nil?

          AdminUser.where(id: user_ids).find_each do |user|
            denial = role_change_denial(user, new_role)
            return denial if denial
          end

          nil
        end

        def bulk_status(result)
          if result.errors.any? && result.success_count.zero? && result.failure_count.zero?
            :bad_request
          elsif result.success_count.zero? && result.failure_count.positive?
            :unprocessable_entity
          elsif result.failure_count.zero?
            :ok
          else
            :multi_status
          end
        end

        def bulk_params
          params.permit(:reason, :role).to_h.symbolize_keys # nosemgrep: ruby.lang.security.model-attr-accessible.model-attr-accessible
        end
      end
    end
  end
end
