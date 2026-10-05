require 'net/http'

class FileUsageClient
  class Error < StandardError; end

  def self.usage(owner_ids)
    summary = request_summary
    owners = owner_ids.each_slice(100).flat_map do |batch|
      request_usage(batch).fetch(:owners)
    end

    {
      file_count: summary.fetch(:file_count),
      total_bytes: summary.fetch(:total_bytes),
      owners: owners
    }
  end

  def self.request_summary
    base_url = ENV.fetch('FILE_SERVICE_URL', 'http://file-service:8082')
    uri = URI.parse("#{base_url.chomp('/')}/internal/usage/summary")
    response = http_client(uri).request(Net::HTTP::Get.new(uri))
    raise Error, "file service returned HTTP #{response.code}" unless response.code.to_i.between?(200, 299)

    parse_summary(response.body)
  rescue Error
    raise
  rescue StandardError => e
    raise Error, e.message
  end

  def self.request_usage(owner_ids)
    base_url = ENV.fetch('FILE_SERVICE_URL', 'http://file-service:8082')
    uri = URI.parse("#{base_url.chomp('/')}/internal/usage")

    request = Net::HTTP::Post.new(uri)
    request['Content-Type'] = 'application/json'
    request.body = { owner_ids: owner_ids }.to_json
    response = http_client(uri).request(request)
    raise Error, "file service returned HTTP #{response.code}" unless response.code.to_i.between?(200, 299)

    parse_response(response.body)
  rescue Error
    raise
  rescue StandardError => e
    raise Error, e.message
  end

  def self.http_client(uri)
    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = uri.scheme == 'https'
    http.open_timeout = 2
    http.read_timeout = 5
    http
  end

  def self.parse_summary(body)
    response = JSON.parse(body)
    {
      file_count: integer_value(response.fetch('file_count')),
      total_bytes: integer_value(response.fetch('total_bytes'))
    }
  rescue JSON::ParserError, KeyError, TypeError, ArgumentError => e
    raise Error, e.message
  end
  private_class_method :parse_summary

  def self.parse_response(body)
    response = JSON.parse(body)
    owners = response.fetch('owners').map do |owner|
      {
        owner_id: owner.fetch('owner_id'),
        file_count: integer_value(owner.fetch('file_count')),
        total_bytes: integer_value(owner.fetch('total_bytes'))
      }
    end

    {
      file_count: integer_value(response.fetch('file_count')),
      total_bytes: integer_value(response.fetch('total_bytes')),
      owners: owners
    }
  rescue JSON::ParserError, KeyError, TypeError, ArgumentError => e
    raise Error, e.message
  end
  private_class_method :parse_response

  def self.integer_value(value)
    raise TypeError, 'usage values must be integers' unless value.is_a?(Integer)

    value
  end
  private_class_method :integer_value
  private_class_method :http_client
  private_class_method :request_summary
  private_class_method :request_usage
end
