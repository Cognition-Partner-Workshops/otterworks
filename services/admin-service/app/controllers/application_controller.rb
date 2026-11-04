class ApplicationController < ActionController::API
  ADMIN_ROLES = %w[ADMIN OWNER].freeze
  ADMIN_USER_ROLE_RANK = { 'viewer' => 0, 'editor' => 1, 'admin' => 2, 'super_admin' => 3 }.freeze

  before_action :require_admin!
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
    Array(request.env['jwt.user_roles'])
  end

  def require_admin!
    return if current_user_roles.intersect?(ADMIN_ROLES)

    render json: { error: 'Admin role required' }, status: :forbidden
  end

  def caller_admin_user
    return @caller_admin_user if defined?(@caller_admin_user)

    @caller_admin_user = current_user_id.present? ? AdminUser.active.find_by(id: current_user_id) : nil
  end

  # OWNER tokens and active super_admin records may assign any role; nobody else may assign roles.
  def caller_role_rank
    return ADMIN_USER_ROLE_RANK['super_admin'] if current_user_roles.include?('OWNER')
    return ADMIN_USER_ROLE_RANK['super_admin'] if caller_admin_user&.role == 'super_admin'

    nil
  end

  # Returns an error message when the caller may not set +new_role+ on +target+, nil when allowed.
  def role_change_denial(target, new_role)
    rank = caller_role_rank
    return 'Only an owner or super_admin may change roles' if rank.nil?
    return 'You may not change your own role' if target.id.to_s == current_user_id.to_s
    return 'You may not change the role of a user above your own' if ADMIN_USER_ROLE_RANK.fetch(target.role, 0) > rank
    return 'You may not assign a role above your own' if ADMIN_USER_ROLE_RANK.fetch(new_role.to_s, 0) > rank

    nil
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
