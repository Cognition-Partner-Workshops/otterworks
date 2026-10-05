require 'rails_helper'

RSpec.describe Api::V1::Admin::MetricsController do
  include ActiveSupport::Testing::TimeHelpers

  before { set_jwt_env(request) }

  describe 'GET #summary' do
    before do
      create_list(:admin_user, 2)
      create(:feature_flag, :enabled)
      create(:storage_quota)
    end

    it 'returns metrics summary' do
      get :summary
      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body).to have_key('users')
      expect(body).to have_key('storage')
      expect(body).to have_key('features')
      expect(body).to have_key('announcements')
      expect(body).to have_key('audit')
      expect(body['users']['total']).to eq(2)
      expect(body['features']['enabled']).to eq(1)
    end

    it 'counts only users signed in since 00:00 UTC today' do
      travel_to Time.zone.parse('2026-10-05 12:00:00') do
        AdminUser.delete_all
        create(:admin_user, last_login_at: Time.zone.parse('2026-10-05 00:00:00'))
        create(:admin_user, last_login_at: Time.zone.parse('2026-10-05 11:59:00'))
        create(:admin_user, last_login_at: Time.zone.parse('2026-10-04 23:59:59'))
        create(:admin_user, last_login_at: nil)

        get :summary
        body = JSON.parse(response.body)
        expect(body['users']['signed_in_today']).to eq(2)
      end
    end
  end
end
