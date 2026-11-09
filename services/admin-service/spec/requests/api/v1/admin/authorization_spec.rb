require 'rails_helper'

# Regression coverage for the missing-auth finding: a self-registered user
# (roles: ["USER"]) must not be able to call any /api/v1/admin/* endpoint,
# including role escalation and bulk deletes.
RSpec.describe 'Admin API authorization', type: :request do
  let!(:victim) { create(:admin_user) }
  let(:user_headers) { auth_headers(roles: %w[USER]) }
  let(:admin_headers) { auth_headers(roles: %w[ADMIN USER]) }

  shared_examples 'rejects non-admin callers' do |method, path_proc, body = nil|
    it "#{method.to_s.upcase} #{path_proc.call('ID')} is forbidden for a USER token" do
      public_send(method, path_proc.call(victim.id), params: body, headers: user_headers, as: :json)
      expect(response).to have_http_status(:forbidden)
      expect(JSON.parse(response.body)['error']).to match(/admin role required/)
    end

    it "#{method.to_s.upcase} #{path_proc.call('ID')} is unauthorized without a token" do
      public_send(method, path_proc.call(victim.id), params: body, as: :json)
      expect(response).to have_http_status(:unauthorized)
    end
  end

  include_examples 'rejects non-admin callers', :get, ->(_id) { '/api/v1/admin/users' }
  include_examples 'rejects non-admin callers', :put, ->(id) { "/api/v1/admin/users/#{id}" },
                   { user: { role: 'super_admin' } }
  include_examples 'rejects non-admin callers', :delete, ->(id) { "/api/v1/admin/users/#{id}" }
  include_examples 'rejects non-admin callers', :put, ->(id) { "/api/v1/admin/users/#{id}/suspend" }
  include_examples 'rejects non-admin callers', :post, ->(_id) { '/api/v1/admin/bulk/users' },
                   { operation: 'delete', user_ids: ['ID'] }
  include_examples 'rejects non-admin callers', :get, ->(_id) { '/api/v1/admin/config' }
  include_examples 'rejects non-admin callers', :get, ->(_id) { '/api/v1/admin/features' }
  include_examples 'rejects non-admin callers', :post, ->(_id) { '/api/v1/admin/announcements' },
                   { announcement: { title: 'x', body: 'y', severity: 'info', status: 'draft' } }
  include_examples 'rejects non-admin callers', :get, ->(_id) { '/api/v1/admin/audit-logs' }
  include_examples 'rejects non-admin callers', :get, ->(id) { "/api/v1/admin/quotas/#{id}" }
  include_examples 'rejects non-admin callers', :get, ->(_id) { '/api/v1/admin/metrics/summary' }
  include_examples 'rejects non-admin callers', :get, ->(_id) { '/api/v1/admin/health/services' }
  include_examples 'rejects non-admin callers', :get, ->(_id) { '/api/v1/admin/incidents' }
  include_examples 'rejects non-admin callers', :get, ->(_id) { '/api/v1/admin/settings/auto_investigate' }

  describe 'privilege escalation via PUT /api/v1/admin/users/:id' do
    it 'does not change the role when the caller is not an admin' do
      put "/api/v1/admin/users/#{victim.id}", params: { user: { role: 'super_admin' } },
                                              headers: auth_headers(user_id: victim.id, roles: %w[USER]), as: :json

      expect(response).to have_http_status(:forbidden)
      expect(victim.reload.role).to eq('viewer')
    end

    it 'ignores a legacy singular `role` claim' do
      headers = auth_headers(roles: [], extra_claims: { role: 'super_admin' })
      put "/api/v1/admin/users/#{victim.id}", params: { user: { role: 'super_admin' } }, headers: headers, as: :json

      expect(response).to have_http_status(:forbidden)
      expect(victim.reload.role).to eq('viewer')
    end

    it 'allows an ADMIN token' do
      put "/api/v1/admin/users/#{victim.id}", params: { user: { display_name: 'Renamed' } },
                                              headers: admin_headers, as: :json

      expect(response).to have_http_status(:ok)
      expect(victim.reload.display_name).to eq('Renamed')
    end
  end

  describe 'bulk delete via POST /api/v1/admin/bulk/users' do
    it 'does not delete users when the caller is not an admin' do
      post '/api/v1/admin/bulk/users', params: { operation: 'delete', user_ids: [victim.id] },
                                       headers: user_headers, as: :json

      expect(response).to have_http_status(:forbidden)
      expect(victim.reload.status).not_to eq('deleted')
    end
  end

  describe 'token type pinning' do
    it 'rejects a refresh token even when it carries the ADMIN role' do
      get '/api/v1/admin/users', headers: auth_headers(roles: %w[ADMIN], type: 'refresh')
      expect(response).to have_http_status(:unauthorized)
    end

    it 'rejects a token without a type claim' do
      get '/api/v1/admin/users', headers: auth_headers(roles: %w[ADMIN], type: nil)
      expect(response).to have_http_status(:unauthorized)
    end
  end

  describe 'secret-protected routes stay outside the JWT role check' do
    around do |example|
      previous = ENV.fetch('ALERT_WEBHOOK_SECRET', nil)
      ENV['ALERT_WEBHOOK_SECRET'] = 'alert-secret'
      example.run
    ensure
      previous.nil? ? ENV.delete('ALERT_WEBHOOK_SECRET') : ENV['ALERT_WEBHOOK_SECRET'] = previous
    end

    it 'still answers the alerts webhook with its own secret check instead of the role check' do
      post '/api/v1/admin/alerts/ingest', params: { alerts: [] }, headers: { 'X-Alert-Secret' => 'wrong' }, as: :json
      expect(response).to have_http_status(:unauthorized)

      post '/api/v1/admin/alerts/ingest', params: { alerts: [] }, headers: { 'X-Alert-Secret' => 'alert-secret' },
                                          as: :json
      expect(response).not_to have_http_status(:forbidden)
      expect(response).not_to have_http_status(:unauthorized)
    end
  end

  describe 'controller inheritance guard' do
    it 'routes every JWT-protected admin controller through BaseController' do
      Rails.application.eager_load!
      secret_protected = [Api::V1::Admin::AlertsController, Api::V1::Admin::ChaosController]
      admin_controllers = ApplicationController.descendants.select { |c| c.name.to_s.start_with?('Api::V1::Admin::') }
      admin_controllers -= secret_protected + [Api::V1::Admin::BaseController]

      expect(admin_controllers).not_to be_empty
      admin_controllers.each do |controller|
        expect(controller.ancestors).to include(Api::V1::Admin::BaseController), "#{controller} skips require_admin!"
      end
    end
  end
end
