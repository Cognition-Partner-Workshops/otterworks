require 'rails_helper'

RSpec.describe MetricsAggregator do
  subject(:summary) { described_class.summary }

  it 'returns zeroed metrics on an empty database' do
    expect(summary[:users]).to include(total: 0, active: 0, suspended: 0, recent_signups: 0)
    expect(summary[:storage]).to include(total_allocated_bytes: 0, total_used_bytes: 0, average_usage_percent: 0,
                                         users_over_quota: 0)
    expect(summary[:features]).to eq(total: 0, enabled: 0, disabled: 0)
    expect(summary[:audit][:total_events]).to eq(0)
  end

  it 'emits an ISO-8601 timestamp' do
    expect { Time.iso8601(summary[:timestamp]) }.not_to raise_error
  end

  it 'counts users by status and role' do
    create_list(:admin_user, 2)
    create(:admin_user, :admin)
    create(:admin_user, :suspended)
    users = summary[:users]
    expect(users[:total]).to eq(4)
    expect(users[:active]).to eq(3)
    expect(users[:suspended]).to eq(1)
    expect(users[:by_role]).to eq('viewer' => 3, 'admin' => 1)
  end

  it 'only counts signups from the last 30 days as recent' do
    create(:admin_user)
    create(:admin_user, created_at: 45.days.ago)
    expect(summary[:users][:recent_signups]).to eq(1)
  end

  it 'aggregates storage and average usage percent' do
    create(:storage_quota, quota_bytes: 100, used_bytes: 50)
    create(:storage_quota, quota_bytes: 100, used_bytes: 100, tier: 'pro')
    storage = summary[:storage]
    expect(storage[:total_allocated_bytes]).to eq(200)
    expect(storage[:total_used_bytes]).to eq(150)
    expect(storage[:average_usage_percent]).to eq(75.0)
    expect(storage[:users_over_quota]).to eq(1)
    expect(storage[:by_tier]).to eq('free' => 1, 'pro' => 1)
  end

  it 'counts enabled and disabled feature flags' do
    create(:feature_flag, name: 'qa_one', enabled: true)
    create(:feature_flag, name: 'qa_two', enabled: false)
    create(:feature_flag, name: 'qa_three', enabled: false)
    expect(summary[:features]).to eq(total: 3, enabled: 1, disabled: 2)
  end

  it 'only counts in-window published announcements as active' do
    create(:announcement, :published)
    create(:announcement, :expired)
    create(:announcement)
    create(:announcement, :critical)
    announcements = summary[:announcements]
    expect(announcements[:total]).to eq(4)
    expect(announcements[:active]).to eq(1)
    expect(announcements[:by_severity]).to eq('info' => 3, 'critical' => 1)
  end

  it 'buckets audit events by today / this week and ranks top actions' do
    create_list(:audit_log, 3, action: 'user.suspended')
    create(:audit_log, action: 'user.updated')
    create(:audit_log, action: 'user.updated', created_at: 3.days.ago)
    create(:audit_log, action: 'config.updated', created_at: 10.days.ago)
    audit = summary[:audit]
    expect(audit[:total_events]).to eq(6)
    expect(audit[:events_this_week]).to eq(5)
    expect(audit[:top_actions].keys.first).to eq('user.suspended')
    expect(audit[:top_actions]).not_to have_key('config.updated')
  end

  it 'limits top actions to five' do
    %w[a b c d e f g].each { |a| create(:audit_log, action: "user.#{a}") }
    expect(summary[:audit][:top_actions].size).to eq(5)
  end
end
