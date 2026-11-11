require 'base64'
require 'date'
require 'digest'
require 'json'
require 'jwt'
require 'net/http'
require 'openssl'
require 'securerandom'

module FinanceWarehouse
  # Executes read-only statements through the Snowflake SQL API v2 with key-pair JWT auth.
  class SnowflakeClient
    class Unavailable < StandardError; end

    DEFAULT_QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"admin-service"}'.freeze
    REQUIRED = %i[account user role warehouse database private_key].freeze
    POLL_INTERVAL = 0.5

    attr_reader :query_ids

    def self.settings_from_env(overrides = {})
      config = defined?(Rails) ? Rails.application.config_for(:finance_warehouse).fetch(:snowflake, {}) : {}
      {
        account: ENV.fetch('SNOWFLAKE_ACCOUNT', nil), user: ENV.fetch('SNOWFLAKE_USER', nil),
        role: ENV.fetch('SNOWFLAKE_ROLE', nil), private_key: ENV.fetch('SNOWFLAKE_PRIVATE_KEY', nil),
        warehouse: first(ENV.fetch('SNOWFLAKE_WAREHOUSE', nil), config[:warehouse]),
        database: first(ENV.fetch('SNOWFLAKE_DATABASE', nil), config[:database]),
        schema: config[:schema],
        query_tag: first(ENV.fetch('SNOWFLAKE_QUERY_TAG', nil), config[:query_tag], DEFAULT_QUERY_TAG),
        timeout: Integer(config.fetch(:timeout, 120))
      }.merge(overrides.compact)
    end

    def self.first(*values)
      values.find { |value| !value.to_s.empty? }
    end

    def initialize(transport: nil, **settings)
      @settings = self.class.settings_from_env(settings)
      @transport = transport
      @query_ids = []
    end

    def query(sql, binds = [])
      missing = REQUIRED.select { |key| @settings[key].to_s.empty? }
      raise Unavailable, 'finance warehouse unavailable' unless missing.empty?

      response = request(:post, '/api/v2/statements', statement_body(sql, binds))
      response = poll(response) while response.fetch('code', nil) == '333334'
      @query_ids << response.fetch('statementHandle')
      rows(response)
    rescue Unavailable
      raise
    rescue StandardError, LoadError
      raise Unavailable, 'finance warehouse unavailable'
    end

    private

    def statement_body(sql, binds)
      {
        statement: sql,
        timeout: @settings[:timeout],
        database: @settings[:database],
        schema: @settings[:schema],
        warehouse: @settings[:warehouse],
        role: @settings[:role],
        bindings: binds.each_with_index.to_h { |value, index| [(index + 1).to_s, { type: 'TEXT', value: value&.to_s }] },
        parameters: { query_tag: @settings[:query_tag], timezone: 'UTC' }
      }.compact
    end

    def poll(response)
      sleep POLL_INTERVAL
      request(:get, "/api/v2/statements/#{response.fetch('statementHandle')}")
    end

    def rows(response)
      metadata = response.fetch('resultSetMetaData')
      columns = metadata.fetch('rowType')
      data = response.fetch('data', []).dup
      partitions = metadata.fetch('partitionInfo', []).length
      (1...partitions).each do |partition|
        data.concat(request(:get, "/api/v2/statements/#{response.fetch('statementHandle')}?partition=#{partition}")
                      .fetch('data', []))
      end
      data.map { |row| columns.zip(row).to_h { |column, value| [column.fetch('name'), cast(column, value)] } }
    end

    def cast(column, value)
      return value if value.nil? || column.fetch('type') != 'date'

      Date.new(1970, 1, 1) + Integer(value)
    end

    def request(method, path, body = nil)
      status, payload = transport.call(method, URI.join(base_url, path), headers, body && JSON.generate(body))
      parsed = JSON.parse(payload)
      raise Unavailable, 'finance warehouse unavailable' unless [200, 202].include?(Integer(status))

      parsed
    end

    def transport
      @transport ||= lambda do |method, uri, headers, body|
        request = method == :post ? Net::HTTP::Post.new(uri, headers) : Net::HTTP::Get.new(uri, headers)
        request.body = body if body
        response = Net::HTTP.start(uri.host, uri.port, use_ssl: true, open_timeout: 10,
                                                       read_timeout: @settings[:timeout] + 30) do |http|
          http.request(request)
        end
        [response.code, response.body]
      end
    end

    def base_url
      host = @settings[:account].to_s.downcase.delete_suffix('.snowflakecomputing.com')
      "https://#{host}.snowflakecomputing.com"
    end

    def headers
      {
        'Authorization' => "Bearer #{jwt}",
        'X-Snowflake-Authorization-Token-Type' => 'KEYPAIR_JWT',
        'Content-Type' => 'application/json',
        'Accept' => 'application/json',
        'User-Agent' => 'otterworks-admin-service/1.0'
      }
    end

    def jwt
      key = OpenSSL::PKey::RSA.new(@settings[:private_key])
      fingerprint = "SHA256:#{Base64.strict_encode64(Digest::SHA256.digest(key.public_to_der))}"
      account = @settings[:account].to_s.upcase.split('.').first
      subject = "#{account}.#{@settings[:user].to_s.upcase}"
      now = Time.now.to_i
      JWT.encode({ iss: "#{subject}.#{fingerprint}", sub: subject, iat: now, exp: now + 3540 }, key, 'RS256')
    end
  end
end
