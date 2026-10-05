module Api
  module V1
    module Admin
      class StorageController < ApplicationController
        def usage
          owner_ids = AdminUser.pluck(:id)
          usage = FileUsageClient.usage(owner_ids)
          owner_usage = usage.fetch(:owners).index_by { |owner| owner.fetch(:owner_id) }

          users = owner_ids.map do |user_id|
            file_usage = owner_usage[user_id]
            {
              user_id: user_id,
              file_count: file_usage&.fetch(:file_count) || 0,
              total_bytes: file_usage&.fetch(:total_bytes) || 0
            }
          end

          render json: {
            total_bytes: usage.fetch(:total_bytes),
            file_count: usage.fetch(:file_count),
            generated_at: Time.current.iso8601,
            users: users
          }, status: :ok
        rescue FileUsageClient::Error => e
          Rails.logger.error("File usage request failed: #{e.message}")
          render json: { error: 'File service unavailable' }, status: :bad_gateway
        end
      end
    end
  end
end
