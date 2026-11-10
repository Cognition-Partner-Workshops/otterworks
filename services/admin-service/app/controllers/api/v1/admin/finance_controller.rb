module Api
  module V1
    module Admin
      class FinanceController < ApplicationController
        def dashboard
          render json: FinanceWarehouse::DashboardQueries.new.dashboard
        rescue FinanceWarehouse::DashboardQueries::Disabled
          render json: { error: 'finance warehouse is disabled' }, status: :not_found
        rescue FinanceWarehouse::TeradataClient::Unavailable
          render json: { error: 'finance warehouse unavailable' }, status: :service_unavailable
        end
      end
    end
  end
end
