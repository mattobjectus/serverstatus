# Script to update Instana dashboard with server status from Google Cloud Storage bucket
# This script reads a CSV file from GCS, formats it as a markdown table, and updates an Instana dashboard widget
# It also manages events (alerts) based on service status changes

#
# TODO: 
# 1. only delete the existing alert if it is close to expiration 
# 2. adjust the start time of the new one to be the same as the old one if you delete it
# 3. this means you will have to rememer the full existing event and then decide.
#


import requests
import json
from google.cloud import storage
import os
from flask import Flask, jsonify, request
import time
from datetime import datetime
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

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

def close_eventsx(eventsToClose):
    """
    Alternate method to close multiple events in a single API call (currently unused)
    This attempts to close multiple events at once but may not work reliably
    
    :param eventsToClose: List of event IDs to close
    """
    if (len(eventsToClose) == 0 ):
        return
    
    headers = {
        'Authorization': f'apiToken {api_token}',
        'Content-Type': 'application/json'
    }
    
    # Prepare event data with list of event IDs to close
    event_data = {
        "eventIds": eventsToClose,
        "reasonForClosing": "Issue resolved. Service back online" ,
        "username" : "admin_user",
        "muteAlerts": True
    }

    post_url = f'{base_url}/api/events/settings/manual-close' 
    response = requests.post(post_url, headers=headers, json=event_data)
    if (response.status_code == 500):
        print(response.status_code)
    else:
        print(response.status_code)

def close_events(eventsToClose):
    """
    Closes events in Instana by iterating through each event ID individually
    This is the primary method used to close events when services come back online
    
    :param eventsToClose: List of event IDs to close
    """
    if (len(eventsToClose) == 0 ):
        return
    
    headers = {
        'Authorization': f'apiToken {api_token}',
        'Content-Type': 'application/json'
    }
    
    # Event data includes reason for closing and user information
    event_data = {
        "reasonForClosing": "Issue resolved. Service back online" ,
        "username" : "admin_user",
        "muteAlerts": True
    }

    # Close each event individually via API
    for  event_id in eventsToClose:
        post_url = f'{base_url}/api/events/settings/manual-close/{event_id}' 
        response = requests.post(post_url, headers=headers, json=event_data)
        if (response.status_code == 404):
            print("Tried to close an already closed event")
        elif (response.status_code == 500):
            print("Server failure... might have worked anyway")
        else:
            print(response.status_code)

def find_open_events():
    """
    Retrieves all open events from Instana and categorizes them by service name
    Separates events into offline events (services down) and online events (services up)
    
    :return: Dictionary with 'offline' and 'online' keys, each containing a dict of service names to event ID lists
    """
    headers = {
        'Authorization': f'apiToken {api_token}',
        'Content-Type': 'application/json'
    }

    # Query events with a window size of 2x the event duration to catch recent events
    d2 = duration*2
    list_url = f'{base_url}/api/events?windowSize={d2}'
    response = requests.get(list_url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to list dashboards: {response.status_code} - {response.text}")

    issues = response.json()
    openOnlineEventIds = {}
    openOfflineEvents = {}
    openOfflineEventIds = {}
    
    # Categorize open events by service name and status (offline vs online)
    for issue in issues: 
        if (issue["state"] == "open"):
                serviceName = None
                # Check if this is an offline event
                if (issue["problem"].endswith(offlineSuffix)):
                    serviceName = issue["problem"].removesuffix(offlineSuffix).strip()
                    eventList = openOfflineEventIds.get(serviceName,[])
                    eventList.append(issue["eventId"])
                    openOfflineEventIds[serviceName] = eventList
                    eventList = openOfflineEvents.get(serviceName,[])
                    eventList.append(issue)
                    openOfflineEvents[serviceName] = eventList

                # Check if this is an online event
                if (issue["problem"].endswith(onlineSuffix)):
                    serviceName = issue["problem"].removesuffix(onlineSuffix).strip()                
                    eventList = openOnlineEventIds.get(serviceName,[])
                    eventList.append(issue["eventId"])
                    openOnlineEventIds[serviceName] = eventList

                    
        
    return { "offline": openOfflineEventIds, "online": openOnlineEventIds, "offlineEvents": openOfflineEvents}

def filter_events_about_to_expire(openEvents):
    """
    This method returns any open events that are about to expire so they can be replaced by new events
    :param openEvents:  a dict of service names to an array of associated event objects
    :return: a dict of service names to an array of event ids for events about to expire
    """
    events_about_to_expire = {}
    now_in_millis = time.time_ns() // 1_000_000
    for serviceName in openEvents:
        events = openEvents[serviceName]
        for event in events:
            expireIn =  (event["end"]-now_in_millis)/60000 
            # Format the datetime object into a readable string (e.g., "2023-03-15 13:00:00")
            startTime = datetime.fromtimestamp(event["start"]/1000).strftime("%Y-%m-%d %H:%M:%S")
            endTime = datetime.fromtimestamp(event["end"]/1000).strftime("%Y-%m-%d %H:%M:%S")
            interval = (event["end"]-event["start"])/60000
            print(f"{serviceName} {startTime}-{endTime} [{interval}] will expire in {expireIn} minutes")
            expires_soon = (event["end"]-max_scheduled_execution_interval) <= now_in_millis            
            if (expires_soon):
                print(f"{serviceName} Expired! {startTime}-{endTime} [{interval}] will expire in {expireIn} minutes")
                eventList = events_about_to_expire.get(serviceName,[])
                eventList.append(event)
                events_about_to_expire[serviceName] = eventList            
    return events_about_to_expire



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
        return dashboard_json
    
    # Search for the widget with matching title and update its config
    for widget in widgets:
        title = widget.get("title");
        if (title == widget_title):
            widget["config"] = replacement_config
            return dashboard_json
        
    raise Exception(f"Dashboard not found. Please make a Markdown widget called {widget_title} in the instana dashboard.")


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

def sendAlertEventWhenServiceIsDown(service_name,status,ppid,limoid,replacementEvent):
    """
    Sends a high-severity event to Instana when a service is detected as down
    
    :param service_name: Name of the service
    :param status: Current status (Down/Offline)
    :param ppid: Process ID
    :param limoid: Limo ID
    """
    headers = {
        'Content-Type': 'application/json'
    }
    
    # calc start and stop
    now_in_millis = time.time_ns() // 1_000_000
    if (replacementEvent):
        start = replacementEvent["start"]
        description = replacementEvent["detail"]    
        startTime = datetime.fromtimestamp(now_in_millis/1000).strftime("%Y-%m-%d %H:%M:%S")
    else:
        start = now_in_millis
        startTime = datetime.fromtimestamp(now_in_millis/1000).strftime("%Y-%m-%d %H:%M:%S")
        description = f"The service '{service_name}' has been detected as down since {startTime}. PPID {ppid}, Limo Port: {limoid}"
    
    end = now_in_millis+duration
    calduations = end - start


    
    # Create event with severity 10 (critical) for service down
    event_data = {
        "title": service_name + " "+offlineSuffix,
        "text": description,
        "severity": 10, 
        "timestamp": start,
        "duration": duration
    }

    print(json.dumps(event_data))

    post_url = f'{agent_url}/com.instana.plugin.generic.event' 
    response = requests.post(post_url, headers=headers, json=event_data)
    if response.status_code != 204:
        raise Exception(f"Failed to send event for {service_name}")
    print(f"Alert Sent: {response.status_code}")

def sendAlertEventWhenServiceIsUp(service_name,status,ppid,limoid):
    """
    Sends a positive event to Instana when a service is detected as up
    Uses negative severity to indicate resolution
    
    :param service_name: Name of the service
    :param status: Current status (Up/Online)
    :param ppid: Process ID
    :param limoid: Limo ID
    """
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Create event with severity -1 (resolution) for service up
    event_data = {
        "title": service_name + " "+onlineSuffix,
        "text": "The service "+service_name+" has been detected as up. PPID "+ppid+", LimoId: "+limoid,
        "severity": -1, 
        "duration":duration
    }

    post_url = f'{agent_url}/com.instana.plugin.generic.event' 
    response = requests.post(post_url, headers=headers, json=event_data)
    if response.status_code != 204:
        raise Exception(f"Failed to send event for {service_name}")

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

        # Get currently open events from Instana to manage event lifecycle
        openIssues = find_open_events()
        offlineEventIds = openIssues["offline"]
        offlineEvents = openIssues["offlineEvents"]
        eventsToReplace = filter_events_about_to_expire(offlineEvents)

        eventsToClose = []

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
                serviceName = columns[0]
                
                if (columns[1].capitalize() == 'Down' or columns[1] == 'Offline'):
                    serviceHasOpenDownEvent = len(offlineEventIds.get(finacle_host+"."+serviceName,[])) > 0
                    if (serviceHasOpenDownEvent):
                        eventsToReplaceForService = eventsToReplace.get(finacle_host+"."+serviceName,[])      
                        eventToReplace = None
                        if (eventsToReplaceForService and len(eventsToReplaceForService)):                            
                            eventIdsToClose = []
                            for event in eventsToReplaceForService:
                                eventIdsToClose.append(event["eventId"])
                            close_events(eventIdsToClose)             
                            eventToReplace = eventsToReplaceForService[0]   
                            sendAlertEventWhenServiceIsDown(finacle_host+"."+columns[0],columns[1],columns[2],columns[3],eventToReplace)                        
                    else:
                        sendAlertEventWhenServiceIsDown(finacle_host+"."+columns[0],columns[1],columns[2],columns[3],None)
                else:
                    # Service is up close the offline event if it has one
                    event_ids_to_close = offlineEventIds.get(finacle_host+"."+serviceName,[])
                    close_events(event_ids_to_close)
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

# Define a simple REST endpoint for GET requests
@app.route('/hello', methods=['GET'])
def hello_world():
    # You can access query parameters, e.g., ?name=World
    name = request.args.get('name', 'World')  # Default to 'World' if no 'name' param
    return jsonify({'message': f'Hello, {name}!'}), 200  # Return JSON with HTTP status 200


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
duration = int(os.getenv('EVENT_DURATION','3600000'))  # Event duration in milliseconds (default: 1 hour)
project= os.getenv("PROJECT_NAME")
finacle_host = os.getenv("FINACLE_HOST")
duration = int(os.getenv('EVENT_DURATION','3600000'))  # Event duration in milliseconds (default: 1 hour)
max_scheduled_execution_interval=int(os.getenv("MAX_SCHEDULED_INTERVAL_IN_MILLIS",duration))


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
        time.sleep(5)
elif not as_endpoint and not loop:
    dd = primaryProcessing()
    print(dd)    
elif (as_endpoint):
    print("****** RUNNNING AS AN ENDPOINT ******")
    if __name__ == '__main__':
        app.run(debug=True, host='0.0.0.0', port=5555)