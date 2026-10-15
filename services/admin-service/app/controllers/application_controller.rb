class ApplicationController < ActionController::API
  # Routes on JwtAuthenticator::EXCLUDED_PATHS that verify their own shared-secret header instead of a JWT.
  SECRET_GUARDED_CONTROLLERS = %w[api/v1/admin/alerts api/v1/admin/chaos].freeze

  before_action :require_admin!, unless: :secret_guarded_controller?
  before_action :set_request_metadata

  rescue_from StandardError do |e|
    Rails.logger.error("Unhandled error: #{e.message}")
    render json: { error: 'Internal server error' }, status: :internal_server_error
  end

  rescue_from ActiveRecord::RecordNotFound do
    render json: { error: 'Resource not found' }, status: :not_found
  end

  rescue_from ActiveRecord::RecordInvalid do |e|
    render json: { error: e.message, details: e.record.errors.full_messages }, status: :unprocessable_entity
  end

  rescue_from ActionController::ParameterMissing do |e|
    render json: { error: "Missing parameter: #{e.param}" }, status: :bad_request
  end

  private

  def current_user_id
    request.env['jwt.user_id']
  end

  def current_user_email
    request.env['jwt.user_email']
  end

  def current_user_role
    request.env['jwt.user_role']
  end

  def current_user_roles
    payload = request.env['jwt.payload']
    AdminAuthorization.normalize_roles(current_user_role, payload.is_a?(Hash) ? payload['roles'] : nil)
  end

  def require_admin!
    return if AdminAuthorization.admin?(current_user_roles)

    Rails.logger.warn("Forbidden: user=#{current_user_id.inspect} roles=#{current_user_roles.inspect} " \
                      "#{request.method} #{request.path}")
    render json: { error: 'Forbidden' }, status: :forbidden
  end

  def secret_guarded_controller?
    SECRET_GUARDED_CONTROLLERS.include?(controller_path)
  end

  def set_request_metadata
    @request_metadata = {
      ip_address: request.remote_ip,
      user_agent: request.user_agent
    }
  end

  def paginate(scope)
    page = [(params[:page] || 1).to_i, 1].max
    per_page = [(params[:per_page] || 20).to_i, 100].min.clamp(1, 100)
    total = scope.count

    records = scope.offset((page - 1) * per_page).limit(per_page)

    response.headers['X-Total-Count'] = total.to_s
    response.headers['X-Page'] = page.to_s
    response.headers['X-Per-Page'] = per_page.to_s

    { records: records, total: total, page: page, per_page: per_page }
  end
end
