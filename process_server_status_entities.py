# Script to update Instana dashboard with server status from Google Cloud Storage bucket
# This script reads a CSV file from GCS, formats it as a markdown table, and updates an Instana dashboard widget
# It also manages events (alerts) based on service status changes

#
# TODO: 
# 1. only delete the existing alert if it is close to expiration 
# 2. adjust the start time of the new one to be the same as the old one if you delete it
# 3. this means you will have to rememer the full existing event and then decide.
#

 
from tempfile import template

import requests
import json
from google.cloud import storage
from flask import Flask, jsonify, request
import time
from datetime import datetime
import os
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()


def string_to_int(s):
    s = f"{s}"
    try:
        value = int(s)
        return value
    except ValueError:
        return 0
    
def sendMetrics(service_name, host_name, state, ppid, port):

    if ((state != 1) and (state != 0)):
        state = 1
    
    ppid = string_to_int(ppid)

    port = string_to_int(port)

    if not service_name:
        raise Exception("Service name must be defined")

    if not host_name:
        raise Exception("Host name must be defined")


    metrics_body = '''{
        "resourceMetrics": [
            {
            "resource": {
                "attributes": [
                {
                    "key": "entity.kind",
                    "value": { "stringValue":  "{custom_entity_kind}" }
                },
                {
                    "key": "service.name",
                    "value": { "stringValue": "{host_name}" }
                },
                {
                    "key": "service.instance.id",
                    "value": { "stringValue": "{service_name}" }
                }
                ]
            },
            "scopeMetrics": [
                {
                "scope": {
                    "name": "fincale.service.metrics",
                    "version": "1.0",
                    "droppedAttributesCount": 0
                },
                "metrics": [
                    {
                    "name": "service_status",
                    "description": "0 is down and 1 is up",
                    "unit": "1",
                    "gauge": {
                        "dataPoints": [
                        {
                            "asInt": "{state}"
                        }
                        ]
                    }
                    },
                    {
                    "name": "service_limo_port",
                    "description": "Process id from the service",
                    "unit": "1",
                    "gauge": {
                        "dataPoints": [
                        {
                            "asDouble": "{port}"
                        }
                        ]
                    }
                    },
                    {
                    "name": "service_process_id",
                    "description": "Process id from the service",
                    "unit": "1",
                    "gauge": {
                        "dataPoints": [
                        {
                            "asDouble": "{ppid}"
                        }
                        ]
                    }
                    }

                ],
                "schemaUrl": "https://opentelemetry.io/schemas/1.9.0"
                }
            ],
            "schemaUrl": "https://opentelemetry.io/schemas/1.9.0"
            }    
        ]
        }'''
    
    # this ins kind of ugly so may want try using a dict or something
    metrics_body = metrics_body.replace("{state}",f"{state}").replace("{ppid}",f"{ppid}").replace("{port}",f"{port}")
    metrics_body = metrics_body.replace("{service_name}",f"{service_name}").replace("{host_name}",f"{host_name}").replace("{custom_entity_kind}",f"{custom_entity_kind}")
    #print(json.dumps(json.loads(metrics_body),indent=3))
    json_body = json.loads(metrics_body)
    
    headers = {
        'Content-Type': 'application/json'
    }
    

    post_url = f'{otlp_agent_url}/v1/metrics' 
    response = requests.post(post_url, headers=headers, json=json_body)
    if response.status_code != 200:
        print(response.text)
        raise Exception(f"Failed to send metrics for {service_name}: {response.text}")
    if (state == 1):
        status = "Up"
    else:
        status = "Down"
        
    print(f"Sent Metrics: {service_name} is {status}")


def find_instana_dashboard_id(dashboard_name, base_url, api_token):
    """
    Downloads all custom dashboards from Instana and looks for the one matching the name

    :param dashboard_name:  name of the dashboard to match
    :param base_url: The base URL of your Instana instance (e.g., 'https://your-unit-your-tenant.instana.io')
    :param api_token: Your Instana API token with permissions to read custom dashboards    
    :return returns the id of the dashboard or None
    """
    headers = {
        'Authorization': f'apiToken {api_token}',
        'Content-Type': 'application/json'
    }

    # Step 1: Get the list of accessible custom dashboards
    list_url = f'{base_url}/api/custom-dashboard'
    response = requests.get(list_url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to list dashboards: {response.status_code} - {response.text}")

    dashboards = response.json()

    # Step 2: Download each dashboard
    for dashboard in dashboards:
        dashboard_id = dashboard['id']
        title = dashboard.get('title', dashboard_id);
        found_it =  (title.startswith(dashboard_name));
        if found_it: 
            return dashboard_id;
    return None


def fetch_instana_dashboard(dashboard_id, base_url, api_token):   
    """
    Returns the json for the dashboard in with the specified name
    :param dashboard_id:  dashboard_id of the dashboard to match
    :param base_url: The base URL of your Instana instance (e.g., 'https://your-unit-your-tenant.instana.io')
    :param api_token: Your Instana API token with permissions to read custom dashboards
    """
    headers = {
        'Authorization': f'apiToken {api_token}',
        'Content-Type': 'application/json'
    }


    # Step 1: Get the list of accessible custom dashboards
    get_url = f'{base_url}/api/custom-dashboard/{dashboard_id}'
    response = requests.get(get_url, headers=headers)

    dashboard = response.json()

    if response.status_code != 200:
        print(f"Failed to download dashboard {dashboard_id}: {response.status_code} - {response.text}")
        return None

    dashboard_data = response.json()
    return dashboard_data;
    

def replaceConfigInWidget(dashboard_json,widget_title,replacement_config):
    """
    Finds a widget by title in the dashboard and replaces its config with new content
    
    :param dashboard_json: The dashboard JSON object
    :param widget_title: The title of the widget to update
    :param replacement_config: The new configuration (markdown table) to set
    :return: Updated dashboard JSON
    """
    widgets = dashboard_json.get("widgets")
    if (not widgets):
       raise Exception(f"Widget not found. Please make a Markdown widget called {widget_title} in the instana dashboard.")

    
    # Search for the widget with matching title and update its config
    for widget in widgets:
        title = widget.get("title");
        if (title == widget_title):
            widget["config"] = replacement_config
            return dashboard_json
        
    raise Exception(f"Widget not found. Please make a Markdown widget called {widget_title} in the instana dashboard.")


def updateDashboardOnInstana(dashboard_json):
    """
    Sends the updated dashboard JSON back to Instana via PUT request
    
    :param dashboard_json: The complete dashboard JSON with updates
    :return: Updated dashboard JSON
    """
    headers = {
        'Authorization': f'apiToken {api_token}',
        'Content-Type': 'application/json'
    }
    
    dashboard_id = dashboard_json['id']
    put_url = f'{base_url}/api/custom-dashboard/{dashboard_id}' 
    response = requests.put(put_url, headers=headers, data=json.dumps(dashboard_json))

    if response.status_code == 200:
        print("Dashboard updated successfully!")
    else:
        raise Exception(f"Failed to update dashboard {dashboard_id}: {response.status_code} - {response.text}")        
    return dashboard_json


def splitThis(line):
    chunks = list(filter(str.strip,line.split(" "))) 
    if (len(chunks) == 3):
        # this means no PPID was provided and so we need to use the ppid in the report
        # as the limo port and blank the pp
        chunks.append('')
        chunks[3] = chunks[2]
        chunks[2] = ''
    return chunks

def processBucketCreateMarkupAndSendEvents(bucket_name,file_path):
    """
    Main processing function that:
    1. Reads CSV file from Google Cloud Storage bucket
    2. Parses the CSV or text file and builds a markdown table
    3. Retrieves open events from Instana
    4. Sends new events for services that are down
    5. Closes events for services that are back up
    
    :param bucket_name: Name of the GCS bucket
    :param file_path: Path to the CSV file in the bucket
    :return: Markdown table string or None
    """

    if local_file_override_path:
        file = open(local_file_override_path)
        content = file.read()
        csv_file = local_file_override_path.endswith('.csv')
    else:
        # Initialize the Google Cloud Storage client (assumes authentication is set up)
        client = storage.Client(project=project)

        # Get the bucket
        bucket = client.get_bucket(bucket_name)

        # Get the blob (file)
        blob = bucket.blob(file_path)
        csv_file = file_path.endswith('.csv')

        # Read the content as text (recommended over download_as_string, which is deprecated)
        content = blob.download_as_text(encoding='utf-8')

    # Parse the content line by line and build a markdown table
    lines = content.strip().split('\n')

    if lines:
        # Build markdown table string
        markdown_table = ""
        
        # Process header row
        # Using &nbsp; for better formatting in Instana dashboard
        header = ["Service Name","Status","PPID","Limo Port"]
        markdown_table += "|&nbsp;" + "&nbsp;|&nbsp;".join(header) + "&nbsp;|\n"
        markdown_table += "| " + " |".join(['---'] * len(header)) + " |\n"
        markdown_table += "|&nbsp; | | | |\n"

        findBreak = '---------------------------------------------------------------------------------|'
        findBreakCount = 3
        lineIndex = 1
        if (not csv_file):
            for line in lines:
                lineIndex = lineIndex + 1
                if (line.strip().endswith(findBreak)):
                    findBreakCount = findBreakCount - 1
                    if (findBreakCount <= 0):
                        break
        else:
            lineIndex = 1
          
        # First pass: Add all offline/down services to the table (in bold)
        addedDowns = False
        for line in lines[lineIndex:]:
            if (not csv_file and line.endswith(findBreak)):
                break
            if line.strip():  # Skip empty lines
                if (csv_file):
                    columns = line.split(',')
                else:
                    columns = splitThis(line)
                if (columns[1].capitalize() == 'Down' or columns[1] == 'Offline'):
                    addedDowns = True
                    markdown_table += "|&nbsp;**" + "**&nbsp;|&nbsp;**".join(columns) + "**&nbsp;|\n"

        if (addedDowns):
            markdown_table += "|&nbsp; | | | |\n"

        # Second pass: Process each service for event management and add online services to table
        for line in lines[lineIndex:]:
            if (not csv_file and line.endswith(findBreak)):
                break
            if line.strip():  # Skip empty lines
                if (csv_file):
                    columns = line.split(',')
                else:
                    columns = splitThis(line)
                service_name = columns[0]
                ppid = columns[2]                
                limo_port = columns[3]
                
                if (columns[1].capitalize() == 'Down' or columns[1] == 'Offline'):
                    sendMetrics(service_name,finacle_host,0,ppid,limo_port)
                else:
                    sendMetrics(service_name,finacle_host,1,ppid,limo_port)
                    # Service is up: add to table and send up event, close offline events
                    markdown_table += "|&nbsp;" + "&nbsp;|&nbsp;".join(columns) + "&nbsp;|\n"
        
        now = datetime.now()
        formatted_time = now.strftime("%d-%m-%Y %H:%M:%S")
        markdown_table += "\n\n##### Updated: "+formatted_time
        return markdown_table
    return None

# =============================================================================
# Primary Processing
# =============================================================================

def primaryProcessing():
        # Step 1: Process the CSV from bucket, create markdown table, and send events
    newConfig = processBucketCreateMarkupAndSendEvents(bucket_name,bucket_file_path)

    # Step 2: Find the dashboard by name
    dashboard_id = find_instana_dashboard_id(dashboard_name,base_url,api_token)

    dashboard_data = f'Dashboard {dashboard_name} not found.'
    if (dashboard_id):
        # Step 3: Fetch the current dashboard configuration
        dashboard_data = fetch_instana_dashboard(dashboard_id,base_url, api_token)

        if (dashboard_data):
            # Step 4: Replace the widget config with the new markdown table
            dashboard_data = replaceConfigInWidget(dashboard_data,widget_name,newConfig)
            
            # Step 5: Update the dashboard on Instana
            updateDashboardOnInstana(dashboard_data)
    return dashboard_data

    
# Create a Flask application instance
app = Flask(__name__)


@app.route('/api/v1/service/status', methods=['GET'])
def executeServiceStatus():
    dd = primaryProcessing()
    return dd


# =============================================================================
# CONFIGURATION SECTION
# =============================================================================
# TODO: ADD ERROR HANDLING
# TODO: HAVE IT RUN AS A SCHEDULED TASK ON CLOUD RUN
# TODO: EXPOSE AN ENDPOINT TO MANUALLY DO IT
# TODO: ADD CODE TO DETECT STATE CHANGE SO WE CAN TOGGLE THE ALERT AND CHANGE SEVERITY
# TODO: ADD LOGGING

# Event title suffixes to identify service status
offlineSuffix = "is Offline"  # Suffix for services that are down
onlineSuffix = "is Online"   # Suffix for services that are up

# Load configuration from environment variables with defaults
base_url = os.getenv('BASE_URL','https://yellow-fire04qg8u.instana.io')  # Instana instance URL
api_token = os.getenv('API_TOKEN','API TOKEN REQUIRED')  # Instana API token
dashboard_name = os.getenv('DASHBOARD_NAME','Finacle Monitor')  # Dashboard name to update
widget_name = os.getenv('WIDGET_NAME','Service Status')  # Widget name within dashboard
bucket_name = os.getenv('BUCKET_NAME','antarsia_test')  # GCS bucket name
bucket_file_path= os.getenv('BUCKET_FILE_PATH','server_status.csv')  # CSV file path in bucket
agent_url  = os.getenv('AGENT_URL','http://172.16.0.70:4001')  # Instana agent URL for events
otlp_agent_url  = os.getenv('OTLP_AGENT_URL','http://172.16.0.70:4000')  # Instana agent URL for events
duration = int(os.getenv('EVENT_DURATION','3600000'))  # Event duration in milliseconds (default: 1 hour)
project= os.getenv("PROJECT_NAME")
finacle_host = os.getenv("FINACLE_HOST")
duration = int(os.getenv('EVENT_DURATION','3600000'))  # Event duration in milliseconds (default: 1 hour)
max_scheduled_execution_interval=int(os.getenv("MAX_SCHEDULED_INTERVAL_IN_MILLIS",duration))
local_file_override_path=os.getenv("USE_LOCAL_FILE_INSTEAD_OF_BUCKET_PATH",None)
skip_events=os.getenv("SKIP_EVENT_GENERATION",'False').lower().startswith('t')
custom_entity_kind="fincacle.service.entity.1"

# =============================================================================
# MAIN EXECUTION FUNCTION
# =============================================================================

as_endpoint=os.getenv("AS_ENDPOINT",'False').lower().startswith('t')
loopTime = int(os.getenv("LOOP_PAUSE_IN_SECONDS","30"))
loop=loopTime >= 0
if loop and not as_endpoint:
    count = 0
    while True:
        count += 1
        print(f"{count} ------------------")        
        dd = primaryProcessing()
        print(f"{count} ------------------")        
        time.sleep(loopTime)
elif not as_endpoint and not loop:
    dd = primaryProcessing()
    print(dd)    
elif (as_endpoint):
    print("****** RUNNNING AS AN ENDPOINT ******")
    if __name__ == '__main__':
        app.run(debug=True, host='0.0.0.0', port=5555)