module Api
  module V1
    module Admin
      class UsersController < ApplicationController
        before_action :set_user, only: %i[show update destroy suspend activate]

        # GET /api/v1/admin/users
        def index
          scope = AdminUser.includes(:storage_quota)
          scope = scope.search(params[:q]) if params[:q].present?
          scope = scope.by_role(params[:role]) if params[:role].present?
          scope = scope.where(status: params[:status]) if params[:status].present?
          scope = scope.order(created_at: :desc)

          result = paginate(scope)

          render json: {
            users: ActiveModelSerializers::SerializableResource.new(result[:records], include_quota: true),
            total: result[:total],
            page: result[:page],
            per_page: result[:per_page]
          }
        end

        # GET /api/v1/admin/users/:id
        def show
          render json: @user, serializer: AdminUserSerializer, include_quota: true
        end

        # PUT /api/v1/admin/users/:id
        def update
          previous_attributes = @user.attributes.slice('role', 'display_name', 'email')
          attributes = user_params
          new_role = role_param

          if new_role && new_role != @user.role
            denial = role_change_denial(@user, new_role)
            return render json: { error: denial }, status: :forbidden if denial
          end
          attributes = attributes.merge(role: new_role) if new_role

          if @user.update(attributes)
            AuditLogger.log(
              action: 'user.updated',
              resource_type: 'AdminUser',
              resource_id: @user.id,
              request: request,
              changes_made: { before: previous_attributes,
                              after: @user.attributes.slice('role', 'display_name', 'email') }
            )
            render json: @user, serializer: AdminUserSerializer, include_quota: true
          else
            render json: { error: 'Validation failed', details: @user.errors.full_messages },
                   status: :unprocessable_entity
          end
        end

        # DELETE /api/v1/admin/users/:id
        def destroy
          @user.soft_delete!

          AuditLogger.log(
            action: 'user.deleted',
            resource_type: 'AdminUser',
            resource_id: @user.id,
            request: request
          )

          head :no_content
        end

        # PUT /api/v1/admin/users/:id/suspend
        def suspend
          @user.suspend!(reason: params[:reason])

          AuditLogger.log(
            action: 'user.suspended',
            resource_type: 'AdminUser',
            resource_id: @user.id,
            request: request,
            changes_made: { reason: params[:reason] }
          )

          render json: @user, serializer: AdminUserSerializer, include_quota: true
        end

        # PUT /api/v1/admin/users/:id/activate
        def activate
          @user.activate!

          AuditLogger.log(
            action: 'user.activated',
            resource_type: 'AdminUser',
            resource_id: @user.id,
            request: request
          )

          render json: @user, serializer: AdminUserSerializer, include_quota: true
        end

        private

        def set_user
          @user = AdminUser.includes(:storage_quota).find(params[:id]) # nosemgrep: ruby.rails.security.brakeman.check-unscoped-find.check-unscoped-find
        end

        def user_params
          params.require(:user).permit(:email, :display_name, :avatar_url)
        end

        def role_param
          role = params.require(:user).permit(:role)[:role]
          role&.to_s
        end
      end
    end
  end
end
