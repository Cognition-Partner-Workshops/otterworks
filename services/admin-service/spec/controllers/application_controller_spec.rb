require 'rails_helper'

RSpec.describe ApplicationController do
  controller do
    def index
      case params[:failure]
      when 'missing' then raise ActiveRecord::RecordNotFound
      when 'invalid'
        record = AdminUser.new
        record.valid?
        raise ActiveRecord::RecordInvalid, record
      when 'parameter' then params.require(:required_field)
      else raise StandardError, 'private diagnostic'
      end
    end
  end

  it 'returns the public 404 error shape' do
    get :index, params: { failure: 'missing' }
    expect(response).to have_http_status(:not_found)
    expect(JSON.parse(response.body)).to eq('error' => 'Resource not found')
  end

  it 'returns validation details with 422' do
    get :index, params: { failure: 'invalid' }
    expect(response).to have_http_status(:unprocessable_entity)
    expect(JSON.parse(response.body)['details']).to include("Email can't be blank")
  end

  it 'names missing parameters in the 400 response' do
    get :index, params: { failure: 'parameter' }
    expect(response).to have_http_status(:bad_request)
    expect(JSON.parse(response.body)).to eq('error' => 'Missing parameter: required_field')
  end

  it 'hides unexpected exception details behind the 500 error shape' do
    get :index
    expect(response).to have_http_status(:internal_server_error)
    expect(JSON.parse(response.body)).to eq('error' => 'Internal server error')
  end
end
