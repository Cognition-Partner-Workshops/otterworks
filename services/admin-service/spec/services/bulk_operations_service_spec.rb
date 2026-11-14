require 'rails_helper'

RSpec.describe BulkOperationsService do
  let!(:users) { create_list(:admin_user, 3) }
  let(:user_ids) { users.map(&:id) }

  describe '.process' do
    it 'suspends users in bulk' do
      result = described_class.process(operation: 'suspend', user_ids: user_ids)
      expect(result.success_count).to eq(3)
      expect(result.failure_count).to eq(0)
      expect(users.map { |u| u.reload.status }.uniq).to eq(['suspended'])
    end

    it 'activates users in bulk' do
      users.each(&:suspend!)
      result = described_class.process(operation: 'activate', user_ids: user_ids)
      expect(result.success_count).to eq(3)
      expect(users.map { |u| u.reload.status }.uniq).to eq(['active'])
    end

    it 'soft deletes users in bulk' do
      result = described_class.process(operation: 'delete', user_ids: user_ids)
      expect(result.success_count).to eq(3)
      expect(users.map { |u| u.reload.status }.uniq).to eq(['deleted'])
    end

    it 'updates roles in bulk' do
      result = described_class.process(operation: 'update_role', user_ids: user_ids, params: { role: 'editor' },
                                       actor_roles: ['admin'])
      expect(result.success_count).to eq(3)
      expect(users.map { |u| u.reload.role }.uniq).to eq(['editor'])
    end

    it 'refuses role changes without an admin actor' do
      result = described_class.process(operation: 'update_role', user_ids: user_ids, params: { role: 'editor' })
      expect(result.failure_count).to eq(3)
      expect(users.map { |u| u.reload.role }.uniq).to eq(['viewer'])
    end

    it 'refuses to grant super_admin unless the actor is a super_admin' do
      result = described_class.process(operation: 'update_role', user_ids: user_ids, params: { role: 'super_admin' },
                                       actor_roles: ['admin'])
      expect(result.failure_count).to eq(3)
      expect(users.map { |u| u.reload.role }.uniq).to eq(['viewer'])

      result = described_class.process(operation: 'update_role', user_ids: user_ids, params: { role: 'super_admin' },
                                       actor_roles: ['super_admin'])
      expect(result.success_count).to eq(3)
    end

    it 'returns error for invalid operation' do
      result = described_class.process(operation: 'invalid', user_ids: user_ids)
      expect(result.errors).to include('Invalid operation: invalid')
    end

    it 'reports missing users' do
      result = described_class.process(operation: 'suspend', user_ids: user_ids + [SecureRandom.uuid])
      expect(result.success_count).to eq(3)
      expect(result.failure_count).to eq(1)
    end
  end
end
