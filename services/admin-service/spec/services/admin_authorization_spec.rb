require 'rails_helper'

RSpec.describe AdminAuthorization do
  describe '.role_from' do
    it 'selects the highest recognized role from both claim formats' do
      expect(described_class.role_from('role' => 'editor', 'roles' => %w[VIEWER ADMIN])).to eq('admin')
      expect(described_class.role_from('role' => 'ADMIN', 'roles' => %w[SUPER_ADMIN VIEWER])).to eq('super_admin')
    end

    it 'denies unknown, missing and malformed role claims' do
      [{}, { 'role' => 'owner' }, { 'roles' => 'SUPER_ADMIN' },
       { 'role' => ['super_admin'], 'roles' => [nil, 1, 'USER'] }].each do |payload|
        expect(described_class.role_from(payload)).to be_nil
      end
    end
  end

  describe '.permitted?' do
    it 'reserves finance dashboard reads for admins and super admins' do
      %w[admin super_admin].each do |role|
        expect(described_class.permitted?(role, 'finance', 'dashboard')).to be true
      end
      %w[viewer editor].each do |role|
        expect(described_class.permitted?(role, 'finance', 'dashboard')).to be false
      end
      expect(described_class.permitted?(nil, 'finance', 'dashboard')).to be false
      expect(described_class.permitted?('admin', 'finance', 'update')).to be false
    end

    it 'keeps viewers read-only and editors limited to content changes' do
      expect(described_class.permitted?('viewer', 'users', 'index')).to be true
      expect(described_class.permitted?('viewer', 'announcements', 'create')).to be false
      expect(described_class.permitted?('editor', 'announcements', 'create')).to be true
      expect(described_class.permitted?('editor', 'features', 'update')).to be true
      expect(described_class.permitted?('editor', 'users', 'update')).to be false
    end

    it 'reserves configuration for super admins and denies unknown actions and roles' do
      expect(described_class.permitted?('admin', 'config', 'index')).to be false
      expect(described_class.permitted?('super_admin', 'config', 'update')).to be true
      expect(described_class.permitted?('super_admin', 'users', 'unknown')).to be false
      expect(described_class.permitted?(nil, 'users', 'index')).to be false
      expect(described_class.permitted?('owner', 'users', 'index')).to be false
    end
  end

  describe '.scope' do
    it 'returns the permitted resource relation' do
      expect(described_class.scope('viewer', Announcement, 'show')).to be_an(ActiveRecord::Relation)
    end

    it 'rejects unauthorized actions and unregistered resources' do
      expect { described_class.scope('viewer', Announcement, 'destroy') }.to raise_error(described_class::Forbidden)
      expect { described_class.scope('admin', SystemConfig, 'show') }.to raise_error(described_class::Forbidden)
      expect { described_class.scope('super_admin', ApplicationRecord, 'show') }.to raise_error(described_class::Forbidden)
    end
  end
end
