require_relative 'spec_helper'
require 'tmpdir'

RSpec.describe ContractWarehouse::EmulatorWarehouse do
  around do |example|
    original = ENV.to_h.slice('CONTRACT_KIT_PYTHON', 'WAREHOUSE_CONTRACT_TARGET', 'CONTRACT_RECORD')
    ENV['CONTRACT_KIT_PYTHON'] = 'python3'
    ENV['WAREHOUSE_CONTRACT_TARGET'] = 'teradata-emulator'
    ENV.delete('CONTRACT_RECORD')
    example.run
  ensure
    %w[CONTRACT_KIT_PYTHON WAREHOUSE_CONTRACT_TARGET CONTRACT_RECORD].each { |key| ENV.delete(key) }
    ENV.update(original)
  end

  it 'passes validated argv directly and SQL through stdin' do
    status = double(success?: true)
    bridge = File.expand_path('../../../consumers/contract-kit/bridge.py', __dir__)
    sql = File.read(File.join(__dir__, 'legacy/dashboard-summary.sql'))
    expect(Open3).to receive(:capture3).with(['python3', 'python3'], bridge,
      '--target', 'teradata-emulator', '--query', 'dashboard-summary', stdin_data: sql)
      .and_return(['{"rows":[],"columns":[]}', '', status])
    expect(described_class.new.query(FinanceWarehouse::DashboardQueries::SUMMARY_SQL)).to eq([])
  end

  it 'rejects executable strings, missing paths and targets before spawning' do
    expect(Open3).not_to receive(:capture3)
    ['', 'python3;touch injected', 'python3 -c code', '/bin/sh', '/missing/python3'].each do |python|
      ENV['CONTRACT_KIT_PYTHON'] = python
      expect { described_class.new.query(FinanceWarehouse::DashboardQueries::SUMMARY_SQL) }
        .to raise_error(ArgumentError)
    end
    ENV['CONTRACT_KIT_PYTHON'] = 'python3'
    ENV['WAREHOUSE_CONTRACT_TARGET'] = 'teradata-emulator;touch injected'
    expect { described_class.new.query(FinanceWarehouse::DashboardQueries::SUMMARY_SQL) }
      .to raise_error(ArgumentError)
  end

  it 'rejects unknown SQL before spawning' do
    expect(Open3).not_to receive(:capture3)
    expect { described_class.new.query('SELECT 1;touch injected') }.to raise_error(KeyError)
  end

  it 'preserves an executable path containing spaces' do
    Dir.mktmpdir('python env ') do |directory|
      python = File.join(directory, 'python3')
      File.write(python, '')
      File.chmod(0o755, python)
      ENV['CONTRACT_KIT_PYTHON'] = python
      expect(Open3).to receive(:capture3).with([python, python], anything, anything, anything,
        anything, anything, stdin_data: anything)
        .and_return(['{"rows":[],"columns":[]}', '', double(success?: true)])
      expect(described_class.new.query(FinanceWarehouse::DashboardQueries::SUMMARY_SQL)).to eq([])
    end
  end
end
