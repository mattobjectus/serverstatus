

import instana_client
from instana_client.models.custom_entity_model import CustomEntityModel
from instana_client.models.custom_entity_with_metadata import CustomEntityWithMetadata
from instana_client.rest import ApiException
from pprint import pprint
import os
from dotenv import load_dotenv
import requests
# Load environment variables from .env file
load_dotenv()

# TODO update the JSON string below
json = '''{
  "identifiers": [
    "service.instance.id",
    "service.name",
    "entity.kind"
  ],
  "dependencies":[],
  "dashboards":[],
  "label": "Finacle Service Entity",
  "tagFilterExpression": {
    "type": "EXPRESSION",
    "logicalOperator": "AND",
    "elements": [
      {
        "type": "TAG_FILTER",
        "name": "entity.kind",
        "value": "finacle.service.entity.1",
        "operator": "EQUALS",
          "entity": "NOT_APPLICABLE"
      },      
        {
          "type": "TAG_FILTER",
          "name": "service.name",
          "operator": "NOT_BLANK",
          "value": null,
          "entity": "NOT_APPLICABLE"
        },      
        {
          "type": "TAG_FILTER",
          "name": "service.instance.id",
          "operator": "NOT_BLANK",
          "value": null,
          "entity": "NOT_APPLICABLE"
        }
    ]
  },
  "metrics": [
    {
      "id": "service.status",
      "source": "service.status",
      "name": "service.status",
      "label" : "Server Status",
      "description": "1 = Up / Healthy, 0 = Down / Unhealthy",
      "unit": "1",
      "type": "GAUGE",
      "aggregation": "MEAN",
      "formatter": "NUMBER",
      "granularity":"600000"
    },
    {
      "id": "service.process.id",
      "source": "service.process.id",
      "name": "service.process.id",
      "label": "Service Process Id",
      "description": "The process id that the finacle service is running on",
      "unit": "1",
      "type": "GAUGE",
      "aggregation": "MEAN",
      "formatter": "NUMBER",
      "granularity":"600000"
    },
    {
      "id": "service.limo.port",
      "source": "service.limo.port",
      "name": "service.limo.port",
      "label": "Service Limo Port",
      "description": "The port that the finacle service is listening on",
      "unit": "1",
      "type": "GAUGE",
      "aggregation": "MEAN",
      "formatter": "NUMBER",
      "granularity":"600000"
    }
],
    "tags":[]
}'''


# create an instance of CustomEntityModel from a JSON string
custom_entity_model_instance = CustomEntityModel.from_json(json)
# print the JSON string representation of the object
print(custom_entity_model_instance.to_json())

# Defining the host is optional and defaults to https://unit-tenant.instana.io
# See configuration.py for a list of all supported configuration parameters.
configuration = instana_client.Configuration(
    host = os.getenv("BASE_URL")
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: ApiKeyAuth
configuration.api_key['ApiKeyAuth'] = os.getenv("API_TOKEN")

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
#configuration.api_key_prefix['ApiKeyAuth'] = 'apiToken'
# Enter a context with an instance of the API client
api_client = instana_client.ApiClient(
    configuration=configuration
)    
api_client.rest_client.session.verify = False
# Create an instance of the API class
api_instance = instana_client.CustomEntitiesApi(api_client)
    #custom_entity_model = instana_client.CustomEntityModel() # CustomEntityModel | 

try:
    # Create a Custom Entity type
    api_response = api_instance.create_custom_entities(custom_entity_model_instance)
    print("The response of CustomEntitiesApi->create_custom_entities:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling CustomEntitiesApi->create_custom_entities: %s\n" % e)