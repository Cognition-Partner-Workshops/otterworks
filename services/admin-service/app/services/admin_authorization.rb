# Role checks for the admin API. Roles come from the verified JWT: admin-service tokens carry a
# singular `role` claim, auth-service tokens carry a `roles` list (e.g. ["ADMIN", "USER"]).
module AdminAuthorization
  class RoleChangeNotPermitted < StandardError; end

  ADMIN_ROLES = %w[admin super_admin].freeze
  SUPER_ADMIN_ROLES = %w[super_admin].freeze

  module_function

  def normalize_roles(*claims)
    claims.flat_map { |claim| Array(claim) }.compact.map { |role| role.to_s.downcase }.uniq
  end

  def admin?(roles)
    roles.intersect?(ADMIN_ROLES)
  end

  def super_admin?(roles)
    roles.intersect?(SUPER_ADMIN_ROLES)
  end

  # Admins may change roles, but only a super_admin may grant or revoke super_admin.
  def authorize_role_change!(actor_roles:, target:, new_role:)
    return if super_admin?(actor_roles)
    raise RoleChangeNotPermitted, 'Admin role required to change roles' unless admin?(actor_roles)
    return unless SUPER_ADMIN_ROLES.include?(new_role.to_s) || SUPER_ADMIN_ROLES.include?(target.role)

    raise RoleChangeNotPermitted, 'Only a super_admin may grant or revoke the super_admin role'
  end
end
