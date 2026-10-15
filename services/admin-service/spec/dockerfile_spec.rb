require 'spec_helper'

RSpec.describe 'admin-service Docker build context' do
  let(:serviceRoot) { File.expand_path('..', __dir__) }
  let(:dockerfile) { File.read(File.join(serviceRoot, 'Dockerfile')) }
  let(:dockerignorePath) { File.join(serviceRoot, '.dockerignore') }
  let(:dockerignoreEntries) do
    File.readlines(dockerignorePath, chomp: true).map(&:strip).reject { |line| line.empty? || line.start_with?('#') }
  end

  def copy_sources(dockerfile)
    dockerfile.lines.grep(/^\s*(COPY|ADD)\b/).flat_map do |line|
      args = line.split.drop(1).reject { |arg| arg.start_with?('--') }
      args[0...-1]
    end
  end

  it 'does not copy the whole build context or use glob patterns (docker:S6470)' do
    copy_sources(dockerfile).each do |source|
      expect(source).not_to match(%r{\A\.?/?\z}), "Dockerfile copies the entire build context via '#{source}'"
      expect(source).not_to match(/[*?\[]/), "Dockerfile copies via glob pattern '#{source}'"
    end
  end

  it 'ships a .dockerignore next to the Dockerfile' do
    expect(File).to exist(dockerignorePath)
  end

  it 'keeps secrets, specs, logs and tmp out of the image' do
    expect(dockerignoreEntries).to include('config/secrets.yml', 'config/master.key', 'spec/', 'log/', 'tmp/')
  end
end
