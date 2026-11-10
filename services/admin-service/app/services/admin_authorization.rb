class AdminAuthorization
  class Forbidden < StandardError; end
  class InvalidRole < StandardError; end

  READ_ACTIONS = %w[
    users.index users.show announcements.index announcements.show
    features.index features.show audit_logs.index audit_logs.show
    incidents.index incidents.show quotas.show health.services
    metrics.summary settings.auto_investigate
  ].freeze
  CONTENT_ACTIONS = %w[
    announcements.create announcements.update announcements.destroy
    features.create features.update features.destroy
  ].freeze
  ADMIN_ACTIONS = %w[
    users.update users.destroy users.suspend users.activate bulk.users
    incidents.create incidents.update incidents.destroy incidents.trigger_session
    quotas.update settings.update_auto_investigate
  ].freeze
  FINANCE_ACTIONS = %w[finance.dashboard].freeze
  PERMISSIONS = {
    'viewer' => READ_ACTIONS,
    'editor' => (READ_ACTIONS + CONTENT_ACTIONS).freeze,
    'admin' => (READ_ACTIONS + CONTENT_ACTIONS + ADMIN_ACTIONS + FINANCE_ACTIONS).freeze,
    'super_admin' => (READ_ACTIONS + CONTENT_ACTIONS + ADMIN_ACTIONS + FINANCE_ACTIONS + %w[config.index config.show config.update]).freeze
  }.freeze
  RESOURCES = {
    'AdminUser' => 'users', 'Announcement' => 'announcements', 'FeatureFlag' => 'features',
    'AuditLog' => 'audit_logs', 'Incident' => 'incidents', 'SystemConfig' => 'config',
    'StorageQuota' => 'quotas'
  }.freeze

  def self.role_from(payload)
    claims = []
    claims << payload['role'] if payload['role'].is_a?(String)
    claims.concat(payload['roles']) if payload['roles'].is_a?(Array)
    roles = claims.grep(String).map(&:downcase)
    AdminUser::ROLES.find { |role| roles.include?(role) }
  end

  def self.permitted?(role, resource, action)
    PERMISSIONS.fetch(role, []).include?("#{resource}.#{action}")
  end

  def self.scope(role, model, action)
    resource = RESOURCES[model.name]
    raise Forbidden unless resource && permitted?(role, resource, action)

    model.all
  end
end
