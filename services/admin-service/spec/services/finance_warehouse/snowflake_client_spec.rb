require 'rails_helper'

RSpec.describe FinanceWarehouse::SnowflakeClient do
  let(:key) { OpenSSL::PKey::RSA.new(2048) }
  let(:calls) { [] }
  let(:responses) { [] }
  let(:transport) do
    lambda do |method, uri, headers, body|
      calls << { method: method, uri: uri, headers: headers, body: body && JSON.parse(body) }
      responses.shift
    end
  end
  let(:settings) do
    { account: 'org-acct', user: 'svc', role: 'reader', warehouse: 'SFX_D1110_PARITY_WH',
      database: 'SFX_D1110_AFTER', schema: 'COMPAT', private_key: key.to_pem }
  end
  let(:client) { described_class.new(transport: transport, **settings) }

  def result(handle, rows, types = [%w[N fixed], %w[D date]])
    [200, JSON.generate(
      'statementHandle' => handle,
      'resultSetMetaData' => { 'rowType' => types.map { |name, type| { 'name' => name, 'type' => type } } },
      'data' => rows
    )]
  end

  it 'posts the statement with the consumer query tag, binds and parity warehouse' do
    responses << result('q-1', [['1.50', '20400']])
    rows = client.query('SELECT ?', ['2026-11-09'])

    expect(rows).to eq([{ 'N' => '1.50', 'D' => Date.new(2025, 11, 8) }])
    request = calls.first
    expect(request[:uri].to_s).to eq('https://org-acct.snowflakecomputing.com/api/v2/statements')
    expect(request[:body]).to include('warehouse' => 'SFX_D1110_PARITY_WH', 'database' => 'SFX_D1110_AFTER',
                                      'schema' => 'COMPAT', 'role' => 'reader')
    expect(request[:body].dig('parameters', 'query_tag'))
      .to eq('{"run":"sfx-d1110","act":"consumers","consumer":"admin-service"}')
    expect(request[:body]['bindings']).to eq('1' => { 'type' => 'TEXT', 'value' => '2026-11-09' })
    expect(request[:headers]['X-Snowflake-Authorization-Token-Type']).to eq('KEYPAIR_JWT')
    expect(client.query_ids).to eq(['q-1'])
  end

  it 'signs a key-pair JWT for the account user' do
    responses << result('q-1', [])
    client.query('SELECT 1')
    token = calls.first[:headers]['Authorization'].delete_prefix('Bearer ')
    payload, = JWT.decode(token, key.public_key, true, algorithm: 'RS256')
    expect(payload['sub']).to eq('ORG-ACCT.SVC')
    expect(payload['iss']).to start_with('ORG-ACCT.SVC.SHA256:')
  end

  it 'polls running statements and reads every partition' do
    responses << [202, JSON.generate('code' => '333334', 'statementHandle' => 'q-2')]
    responses << [200, JSON.generate(
      'statementHandle' => 'q-2', 'data' => [['1']],
      'resultSetMetaData' => { 'rowType' => [{ 'name' => 'N', 'type' => 'fixed' }], 'partitionInfo' => [{}, {}] }
    )]
    responses << [200, JSON.generate('data' => [['2']])]
    allow(client).to receive(:sleep)

    expect(client.query('SELECT 1')).to eq([{ 'N' => '1' }, { 'N' => '2' }])
    expect(calls.map { |call| call[:uri].to_s })
      .to eq(%w[statements statements/q-2 statements/q-2?partition=1].map do |path|
        "https://org-acct.snowflakecomputing.com/api/v2/#{path}"
      end)
  end

  it 'raises a sanitized error on warehouse failures' do
    responses << [422, JSON.generate('message' => 'SQL compilation error: secret detail')]
    expect { client.query('SELECT 1') }.to raise_error(described_class::Unavailable, 'finance warehouse unavailable')
  end

  it 'does not connect when credentials are missing' do
    missing = described_class.new(transport: transport, **settings, private_key: nil)
    allow(ENV).to receive(:fetch).and_call_original
    allow(ENV).to receive(:fetch).with('SNOWFLAKE_PRIVATE_KEY', nil).and_return(nil)
    expect { missing.query('SELECT 1') }.to raise_error(described_class::Unavailable)
    expect(calls).to be_empty
  end

  it 'defaults to the parity warehouse and consumer tag from configuration' do
    defaults = described_class.settings_from_env
    expect(defaults).to include(database: 'SFX_D1110_AFTER', schema: 'COMPAT')
    expect(defaults[:query_tag]).to eq(described_class::DEFAULT_QUERY_TAG)
  end
end
