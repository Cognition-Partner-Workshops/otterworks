require 'spec_helper'
require 'active_support'
require 'active_support/configuration_file'

RSpec.describe 'config/database.yml' do
  let(:path) { File.expand_path('../../config/database.yml', __dir__) }

  def parse_with_database_password(value)
    original = ENV.fetch('DATABASE_PASSWORD', nil)
    value.nil? ? ENV.delete('DATABASE_PASSWORD') : ENV['DATABASE_PASSWORD'] = value
    ActiveSupport::ConfigurationFile.parse(path)
  ensure
    original.nil? ? ENV.delete('DATABASE_PASSWORD') : ENV['DATABASE_PASSWORD'] = original
  end

  it 'fails fast when DATABASE_PASSWORD is unset instead of using a committed default' do
    expect { parse_with_database_password(nil) }.to raise_error(KeyError, /DATABASE_PASSWORD/)
  end

  it 'uses DATABASE_PASSWORD from the environment' do
    config = parse_with_database_password('from-env')
    expect(config['production']['password']).to eq('from-env')
  end
end
