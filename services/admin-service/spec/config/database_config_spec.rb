require 'spec_helper'
require 'erb'
require 'yaml'

RSpec.describe 'config/database.yml' do
  let(:template) { File.read(File.expand_path('../../config/database.yml', __dir__)) }

  def render_with_database_password(value)
    original = ENV.fetch('DATABASE_PASSWORD', nil)
    value.nil? ? ENV.delete('DATABASE_PASSWORD') : ENV['DATABASE_PASSWORD'] = value
    ERB.new(template).result
  ensure
    original.nil? ? ENV.delete('DATABASE_PASSWORD') : ENV['DATABASE_PASSWORD'] = original
  end

  it 'fails fast when DATABASE_PASSWORD is unset instead of using a committed default' do
    expect { render_with_database_password(nil) }.to raise_error(KeyError, /DATABASE_PASSWORD/)
  end

  it 'uses DATABASE_PASSWORD from the environment' do
    config = YAML.safe_load(render_with_database_password('from-env'), aliases: true)
    expect(config['production']['password']).to eq('from-env')
  end
end
