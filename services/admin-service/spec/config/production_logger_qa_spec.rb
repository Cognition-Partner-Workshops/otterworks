require 'rails_helper'

RSpec.describe 'config/environments/production.rb logger' do
  it 'uses a logger factory that exists on this Rails version' do
    pending '[PLANTED] production.rb calls ActiveSupport::TaggedLogging.logger, which does not exist on Rails 7.1 ' \
            '(admin-service crash-loops with RAILS_ENV=production; see AGENTS.md)'
    source = Rails.root.join('config/environments/production.rb').read
    expect(source).to include('TaggedLogging.logger')
    expect(ActiveSupport::TaggedLogging).to respond_to(:logger)
  end
end
