ENV['RAILS_ENV'] = 'test'
ENV['JWT_SECRET'] = 'access-control-test-secret'
require_relative '../config/environment'

class AccessProbeController < ApplicationController
  def show
    render json: { ok: true }
  end
end

RSpec.describe 'Admin access control' do
  before(:all) do
    Rails.application.routes.append { get '/access-probe', to: 'access_probe#show' }
    Rails.application.reload_routes!
  end

  def call_path(path, roles: nil, method: 'GET', headers: {})
    if roles
      token = JWT.encode({ sub: 'user-b', roles: roles, exp: 1.hour.from_now.to_i }, ENV.fetch('JWT_SECRET'), 'HS256')
      headers['HTTP_AUTHORIZATION'] = "Bearer #{token}"
    end
    Rack::MockRequest.new(Rails.application).request(method, path, headers)
  end

  it('rejects anonymous callers') { expect(call_path('/access-probe').status).to eq(401) }
  it('rejects USER tokens') { expect(call_path('/access-probe', roles: ['USER']).status).to eq(403) }
  it('accepts ADMIN tokens') { expect(call_path('/access-probe', roles: ['USER', 'ADMIN']).status).to eq(200) }

  %w[ALERT_WEBHOOK_SECRET CHAOS_SECRET].each do |secret|
    path = secret == 'CHAOS_SECRET' ? '/api/v1/admin/chaos' : '/api/v1/admin/alerts/ingest'
    header = secret == 'CHAOS_SECRET' ? 'HTTP_X_CHAOS_SECRET' : 'HTTP_X_ALERT_SECRET'

    it "rejects #{path} when #{secret} is absent outside development" do
      original = ENV.delete(secret)
      allow(Rails).to receive(:env).and_return(ActiveSupport::StringInquirer.new('production'))
      expect(call_path(path, method: 'POST').status).to eq(401)
    ensure
      ENV[secret] = original
    end

    it "rejects incorrect #{secret}" do
      original = ENV[secret]
      ENV[secret] = 'configured-secret'
      expect(call_path(path, method: 'POST', headers: { header => 'wrong-secret' }).status).to eq(401)
    ensure
      ENV[secret] = original
    end

    it "allows the valid #{secret} past authentication without a JWT" do
      original = ENV[secret]
      ENV[secret] = 'configured-secret'
      # Invalid payloads are rejected by the action, not the authentication filter.
      expected_status = secret == 'CHAOS_SECRET' ? 422 : 400
      expect(call_path(path, method: 'POST', headers: { header => 'configured-secret' }).status).to eq(expected_status)
    ensure
      ENV[secret] = original
    end
  end
end
