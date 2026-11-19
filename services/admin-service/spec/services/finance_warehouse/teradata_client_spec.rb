require 'rails_helper'

RSpec.describe FinanceWarehouse::TeradataClient do
  subject(:client) { described_class.new(dsn: 'fake-dsn', connector: connector) }

  let(:connection) { double('ODBC connection') }
  let(:statement) { double('ODBC statement') }
  let(:connector) { ->(_dsn) { connection } }

  before do
    allow(connection).to receive(:run).with('SEL 1').and_return(statement)
    allow(connection).to receive(:disconnect)
    allow(statement).to receive(:drop)
  end

  it 'does not connect at initialization' do
    expect(connection).not_to receive(:run)
    expect(client).to be_a(described_class)
  end

  it 'reads rows and closes resources' do
    allow(statement).to receive(:fetch_hash).and_return({ 'VALUE' => 1 }, nil)
    expect(client.query('SEL 1')).to eq([{ 'VALUE' => 1 }])
    expect(statement).to have_received(:drop)
    expect(connection).to have_received(:disconnect)
  end

  it 'returns empty results' do
    allow(statement).to receive(:fetch_hash).and_return(nil)
    expect(client.query('SEL 1')).to eq([])
  end

  it 'sanitizes query errors and disconnects' do
    allow(connection).to receive(:run).and_raise(StandardError, 'private DSN')
    expect { client.query('SEL 1') }.to raise_error(described_class::Unavailable, 'finance warehouse unavailable')
    expect(connection).to have_received(:disconnect)
  end

  it 'sanitizes a missing optional driver' do
    unavailable = described_class.new(dsn: 'fake-dsn', connector: ->(_dsn) { raise LoadError, 'odbc' })
    expect { unavailable.query('SEL 1') }.to raise_error(described_class::Unavailable)
  end
end
