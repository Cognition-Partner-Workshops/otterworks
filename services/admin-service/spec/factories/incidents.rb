FactoryBot.define do
  factory :incident do
    title { 'Search unavailable' }
    description { 'Search requests are failing' }
    severity { 'high' }
    status { 'open' }
    affected_service { 'search-service' }
  end
end
