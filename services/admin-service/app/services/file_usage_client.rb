require 'net/http'

class FileUsageClient
  class Error < StandardError; end

  def self.usage(owner_ids)
    totals = { file_count: 0, total_bytes: 0, owners: [] }
    owner_ids.each_slice(100) do |batch|
      response = request_usage(batch)
      totals[:file_count] += response.fetch(:file_count)
      totals[:total_bytes] += response.fetch(:total_bytes)
      totals[:owners].concat(response.fetch(:owners))
    end
    totals
  end

  def self.request_usage(owner_ids)
    base_url = ENV.fetch('FILE_SERVICE_URL', 'http://file-service:8082')
    uri = URI.parse("#{base_url.chomp('/')}/internal/usage")
    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = uri.scheme == 'https'
    http.open_timeout = 2
    http.read_timeout = 5

    request = Net::HTTP::Post.new(uri)
    request['Content-Type'] = 'application/json'
    request.body = { owner_ids: owner_ids }.to_json
    response = http.request(request)
    raise Error, "file service returned HTTP #{response.code}" unless response.code.to_i.between?(200, 299)

    parse_response(response.body)
  rescue Error
    raise
  rescue StandardError => e
    raise Error, e.message
  end

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
  private_class_method :request_usage
end
