require 'rails_helper'
require 'open3'

# Boots the app in production mode in a subprocess. On main this is expected to
# fail: config/environments/production.rb calls ActiveSupport::TaggedLogging.logger,
# which does not exist in Rails 7.1 (planted bug — do not fix in QA runs).
RSpec.describe 'production environment boot', :planted_bug do
  it 'loads config/environments/production.rb without raising' do
    env = {
      'RAILS_ENV' => 'production',
      'SECRET_KEY_BASE' => 'qa-secret-key-base',
      'JWT_SECRET' => 'qa-jwt-secret',
      'COVERAGE' => 'false'
    }
    _out, err, status = Open3.capture3(env, 'bundle', 'exec', 'ruby', '-e',
                                       "require './config/environment'; puts Rails.env",
                                       chdir: Rails.root.to_s)
    expect(status).to be_success, "production boot failed:\n#{err.lines.first(3).join}"
  end
end
