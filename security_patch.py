import smtplib
import socket
import config
import json
import time
import logging
import requests
import urllib3
import threading
from datetime import datetime
from notification import send_email, send_slack_notification, send_failslack_notification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ObjectNotFound(Exception):
    pass

class TooManyResults(Exception):
    pass

class NoLastExecutionFound(Exception):
    pass

class ActionFailure(Exception):
    pass

def logging_setup():
    # Get the current logging level from the configuration
    logging_level = config.LOGGING_LEVEL

    # Create a root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if logging_level == 'DEBUG' else logging.INFO)

    # Remove any existing handlers to prevent duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # Add a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if logging_level == 'DEBUG' else logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(console_handler)

# Search project and return its id
def return_project_id():
    url = config.api_url + 'projects/'
    response = requests.get(f'{url}?name={config.security_project_name}', auth=(config.username, config.password), verify=False)

    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")
    if response.status_code != requests.codes.ok:
        raise ObjectNotFound(f"{response.status_code} - Failed to search project: name={config.security_project_name}")

    search_response = response.json()
    if not search_response['count']:
        raise ObjectNotFound(f"{response.status_code} - Project doesn't exist: name={config.security_project_name}")
    else:
        project_id = search_response['results'][0]['id']

    logging.info(f'{response.status_code} - Found project: name={config.security_project_name}, id={project_id}')
    return project_id

#create inventory
def create_inventory(inventory_name, organization_id):
    """Create a new inventory in AWX."""
    url = f"{config.api_url}inventories/"
    payload = {
        "name": inventory_name,
        "organization": organization_id,
        "description": "Security Software install Inventory"
    }
    response = requests.post(url, auth=(config.username, config.password), verify=False, json=payload)
    
    if response.status_code == 201:
        inventory_id = response.json()['id']
        logging.info(f"Inventory '{inventory_name}' created successfully with ID: {inventory_id}")
        return inventory_id
    else:
        logging.error(f"Failed to create inventory: {response.status_code} - {response.text}")
        return None

def delete_inventory(inventory_id, max_retries=5, delay=10):
    """Delete an inventory by its ID, with retries if the deletion is not immediate."""
    for attempt in range(max_retries):
        url = f"{config.api_url}inventories/{inventory_id}/"
        response = requests.delete(url, auth=(config.username, config.password), verify=False)
        logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")

        if response.status_code == 202:
            logging.info(f"{response.status_code} - Inventory deleted successfully: inventory_id={inventory_id}")
            return
    raise ActionFailure(f"Failed to delete inventory {inventory_id} after {max_retries} attempts.")
    
    
def add_host_to_inventory(inventory_id, hostname):
    """Add a host to the specified inventory in AWX."""
    url = f"{config.api_url}inventories/{inventory_id}/hosts/"
    payload = {
        "name": hostname,
        "inventory": inventory_id
    }
    response = requests.post(url, auth=(config.username, config.password), verify=False, json=payload)
    
    if response.status_code == 201:
        logging.info(f"Host '{hostname}' added to inventory successfully.")
    else:
        logging.error(f"Failed to add host '{hostname}': {response.status_code} - {response.text}")

# Search credential and return its id
def return_credential_id(credential):
    url = config.api_url + 'credentials/'
    response = requests.get(f"{url}?name={credential}", auth=(config.username, config.password), verify=False)
    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")

    if response.status_code != requests.codes.ok:
        raise ObjectNotFound(f"{response.status_code} - Failed to search credential: name={credential}")

    search_response = json.loads(response.text)
    count = search_response['count']

    if not count:
        raise ObjectNotFound(f"{response.status_code} - Credential not found: name={credential}")
    elif search_response['count'] > 1:
        raise TooManyResults(f"{response.status_code} - Too many credentials found: name={credential} count={search_response['count']}")
    else:
        credential_id = search_response['results'][0]['id']

    logging.info(f"{response.status_code} - Found Credential: name={credential}, id={credential_id}")
    return credential_id

# Search execution environment and return its id
def get_ee_id():
    url = config.api_url + 'execution_environments/'
    response = requests.get(f'{url}?name={config.security_eename}', auth=(config.username, config.password), verify=False)
    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")

    if response.status_code != 200:
        error_message = response.json()
        logging.error(f'{response.status_code} - Error fetching EE id: name={config.security_eename}, msg={error_message}')
        return None

    results = response.json().get('results', [])
    if not results:
        logging.error(f'{response.status_code} - EE not found: name {config.security_eename}, msg: {response.json()}')
        return None

    ee_id = results[0]["id"]
    logging.info(f'{response.status_code} - Found Execution Environment: name={config.security_eename}, id={ee_id}')
    return ee_id

def add_job_template(payload, name, temp_credentials, credentials):
    url = config.api_url + 'job_templates/'
    
    response = requests.post(url, auth=(config.username, config.password), verify=False, json=payload)
    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")
    
    if response.status_code != 201:
        if response.status_code == 400 and "already exists" in response.text:
            logging.info(f"{response.status_code} - Job Template already exists, name={name}")
            logging.info("Updating existing template")
            
            # Updating existing template
            find_template_id = requests.get(f'{url}?name={name}', auth=(config.username, config.password), verify=False)
            results = find_template_id.json().get('results', [])
            
            if not results:
                raise ActionFailure(f"{response.status_code} - Job template not found: name={name}")
            
            job_template_id = results[0]["id"]
            response = requests.put(f'{url}{job_template_id}/', auth=(config.username, config.password), verify=False, json=payload)
            logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")
            
            if response.status_code != 200:
                raise ActionFailure(f"{response.status_code} - Failed to update job template: name={name}")
            
            return job_template_id
        
        if response.status_code == 400 and "Playbook not found for project" in response.text:
            raise ActionFailure(f"{response.status_code} - Failed to add job template: name={name}, msg='Playbook not found for project'")
        
        raise ActionFailure(f"{response.status_code} - Failed to create job template: name={name}, msg={response.text}")
    
    try:
        response_txt = response.json()
        job_template_id = response_txt['id']
    except KeyError:
        raise ActionFailure(f"Unexpected API response: 'id' not found in response: {response_txt}")
    except json.JSONDecodeError:
        raise ActionFailure(f"Failed to parse API response: {response.text}")

    # Attach credentials to job template
    if temp_credentials:
        url = f"{url}{job_template_id}/credentials/"
        for cred_id in temp_credentials:
            payload = {'id': cred_id}
            response = requests.post(url, auth=(config.username, config.password), verify=False, json=payload)
            logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")
            
            if response.status_code != 204:
                raise ActionFailure(f"{response.status_code} - Failed to attach credential to job template: template_name={name}, cred_id={cred_id}, msg={response.text}")
        
        logging.info(f"{response.status_code} - Credentials attached to job template: template_name={name}, credentials={credentials}")
    
    logging.info(f"{response.status_code} - Job template created: name={name}, id={job_template_id}")
    return job_template_id



def run_job_template(job_template_id, name, job_slice_count):
    
    url = f"{config.api_url}job_templates/{job_template_id}/launch/"

    response = requests.post(url, auth=(config.username, config.password), verify=False)
    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")

    if response.status_code != 201:
        # Log the full response for debugging
        logging.error(f"Failed to launch Job Template: template_name={name}, response={response.text}")
        raise ActionFailure(f"{response.status_code} - Failed to launch Job Template: template_name={name}")

    try:
        response_json = response.json()
        if job_slice_count > 1:
            # For workflow jobs, the response contains 'id' instead of 'job'
            job_id = response_json['id']
            job_stdout = response_json.get('related', {}).get('stdout', 'No stdout available for workflow jobs')
        else:
            # For regular jobs, the response contains 'job'
            job_id = response_json['job']
            job_stdout = response_json.get('related', {}).get('stdout', 'No stdout available')

        logging.info(f"{response.status_code} - Job launched successfully: template_name={name}, job id={job_id}")
        return job_id, job_stdout
    except KeyError as e:
        # Log the full response if the expected keys are missing
        logging.error(f"Unexpected API response: {response_json}")
        raise ActionFailure(f"Unexpected API response: missing key {e}")

def check_job_status(job_id, receivers, job_slice_count, inventory_id):
    
    if job_slice_count > 1:
        # Use workflow_jobs API for sliced jobs
        url = f"{config.api_url}workflow_jobs/{job_id}/"
        stdout_url = f"{config.api_url}workflow_jobs/{job_id}/stdout/?format=txt"
    else:
        # Use jobs API for regular jobs
        url = f"{config.api_url}jobs/{job_id}/"
        stdout_url = f"{config.api_url}jobs/{job_id}/stdout/?format=txt"

    while True:
        response = requests.get(url, auth=(config.username, config.password), verify=False)
        logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")

        if response.status_code != 200:
            raise ActionFailure(f"{response.status_code} - Failed to fetch job status: job_id={job_id}")

        job_status = response.json()['status']

        if job_status in ['successful', 'failed', 'error', 'canceled']:
            logging.info(f"{response.status_code} - Job completed with status: {job_status}, job_id={job_id}")

            # Fetch job details
            job_name = response.json().get('name', 'N/A')
            started_at = response.json().get('started', 'N/A')
            job_url = f"https://efvawx-qa.ecp.comcast.com/#/jobs/playbook/{job_id}/output"

            # Fetch job stdout
            stdout_response = requests.get(stdout_url, auth=(config.username, config.password), verify=False)
            if stdout_response.status_code == 200:
                job_stdout = stdout_response.text
                # Extract only the last failed task output
                failed_lines = [line for line in job_stdout.splitlines() if "failed:" in line]
                failed_output = failed_lines[-1] if failed_lines else "No failed output found."
                logging.info(f"Last failed task output for job_id={job_id}:\n{failed_output}")  # Log only the last failed output
            else:
                logging.error(f"Failed to fetch job stdout: {stdout_response.status_code}")
                job_stdout = "No output available."

            # Send email and slack notification if the job failed
            if job_status in ['failed', 'error']:
                subject = f"Job Failed: {job_id}"
                msg = f"""
Hello,

Unfortunately, your job **{job_id}** has **failed**.

**Job Summary:**
- **Job Name:** {job_name}
- **Started At:** {started_at}
- **Job Status:** ❌ Failed

**Error Details:**
{failed_output}

For troubleshooting, check the logs here: {job_url}

Best Regards,
Automation Team
"""
                send_email(receivers, config.smtp_host, config.smtp_port, subject, msg)
                send_failslack_notification(job_id, job_url, job_name, started_at, failed_output)
            elif job_status == 'successful':
               send_slack_notification(job_id, job_url, job_name, started_at)
            
            delete_inventory(inventory_id)
            return job_status, job_stdout

        time.sleep(10)  # Wait for 10 seconds before polling again


def delete_job_template(job_template_id):
    url = f"{config.api_url}job_templates/{job_template_id}/"
    response = requests.delete(url, auth=(config.username, config.password), verify=False)
    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")

    if response.status_code != 204:
        raise ActionFailure(f"{response.status_code} - Failed to delete job template: template_id={job_template_id}")

    logging.info(f"{response.status_code} - Job template deleted: template_id={job_template_id}")

def get_organization_id(org_name):
    """Fetches the organization ID by name."""
    url = f"{config.api_url}organizations/?name={org_name}"
    response = requests.get(url, auth=(config.username, config.password), verify=False)

    if response.status_code == 200 and response.json()["count"] > 0:
        org_id = response.json()["results"][0]["id"]
        logging.info(f"Organization '{org_name}' ID: {org_id}")
        return org_id
    else:
        logging.error(f"Organization '{org_name}' not found.")
        return None

def fetch_job_stdout(job_id):
    """Fetch job stdout from AWX API."""
    stdout_url = f"{config.api_url}jobs/{job_id}/stdout/?format=txt"
    response = requests.get(stdout_url, auth=(config.username, config.password), verify=False)
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch job stdout: {response.status_code} - {response.text}")
    
    return response.text

def is_job_running_with_same_name(job_template_name):
    url = f"{config.api_url}jobs/?job_template__name={job_template_name}"
    response = requests.get(url, auth=(config.username, config.password), verify=False)
    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")

    if response.status_code != 200:
        raise ActionFailure(f"{response.status_code} - Failed to fetch jobs: template_name={job_template_name}")

    jobs = response.json().get('results', [])
    for job in jobs:
        if job['status'] in ['pending', 'running', 'waiting']:
            return True

    return False


def security_main(security_vars):
    # Set up logging
    logging_setup()

    # Default response
    response = {
        "status": "error",
        "message": "An unexpected error occurred.",
        "job_id": None,
        "job_stdout": None,
        "name": None
    }


    try:
        # Fetch organization ID
        organization_id = get_organization_id(config.security_organizations)
        if not organization_id:
            raise ObjectNotFound(f"Organization not found: name={config.security_organizations}")

        project_id = return_project_id()  # Getting project ID
        
        inventory_name = security_vars["inventory_name"]
        inventory_id = create_inventory(inventory_name, organization_id)

        if not inventory_id:
            logging.error("Failed to create inventory. Exiting.")
            return response

        hostnames = security_vars["hostnames"]
        # Add hosts to the inventory
        for hostname in hostnames:
            add_host_to_inventory(inventory_id, hostname)

        temp_credentials = []
        playbook = config.security_playbook
        
        credentials = config.security_credentials  # Getting credentials ID
        if credentials:
            for credential in credentials:
                get_credential_id = return_credential_id(credential)
                temp_credentials.append(get_credential_id)
        else:
            logging.info('200 - No credentials mentioned in config')

        ee_id = get_ee_id()  # Getting execution environment's ID

        # Extract email from the security_vars dictionary
        email = security_vars["email"]
        # Convert email to a list for the receivers parameter
        receivers = [email]
        
        job_tags = security_vars["job_tags"]
        skip_tags = security_vars["skip_tags"]

        # Validate job_slice_count
        job_slice_count = security_vars.get("job_slice_count", 1)  # Default to 1 if not provided
        if not isinstance(job_slice_count, int) or job_slice_count < 1:
            logging.warning(f"Invalid job_slice_count: {job_slice_count}. Defaulting to 1.")
            job_slice_count = 1

        

        name = "PPS-Update"
        # Payload for creating job template
        payload = {
            'name': name,
            'description': 'created by SRF automation',
            'job_type': 'run',
            'inventory': inventory_id,
            'project': project_id,
            'playbook': playbook,
            'execution_environment': ee_id,
            'verbosity': 2,
            'extra_vars': json.dumps(security_vars),
            'job_tags': '',  # Use the comma-separated string for job_tags
            'skip_tags': '',  # Use the comma-separated string for skip_tags
            'become_enabled': '',
            'allow_simultaneous': True  # This enables concurrent jobs
        }

        # Create job template
        job_template_id = add_job_template(payload, name, temp_credentials, credentials)

        if isinstance(job_template_id, int):
            # Check if a job with the same name is already running
            if is_job_running_with_same_name(name):
                raise ActionFailure(f"A job with the same name '{name}' is already running. Please wait for it to complete.")

            # Launch the job template
            job_id, job_stdout = run_job_template(job_template_id, name, job_slice_count)

            # Run check_job_status in a separate thread
            job_thread = threading.Thread(target=check_job_status, args=(job_id, receivers, job_slice_count, inventory_id))
            job_thread.start()  # Start the thread

            # Update response with success details
            response.update({
                "status": "success",
                "job_id": job_id,
                "job_stdout": job_stdout,
                "name": name,
                "message": f"Job for playbook '{playbook}' launched successfully."
            })

            # Wait for the job to complete before proceeding to the next playbook
            #job_thread.join()

        elif isinstance(job_template_id, str) and "already exists" in job_template_id:
            response.update({
                "status": "error",
                "message": f"Job template already exists with name {name}.",
                "name": name
            })
        else:
            raise ActionFailure(f"Can't launch the job as no template id found: template id={job_template_id}")

        logging.info("End of script")
        return response

    except ObjectNotFound as e:
        response["message"] = str(e)
        logging.error(e)
        return response
    except TooManyResults as e:
        response["message"] = str(e)
        logging.error(e)
        return response
    except ActionFailure as e:
        response["message"] = str(e)
        logging.error(e)
        return response
    except Exception as e:
        response["message"] = f"Unexpected error occurred: {e}"
        logging.error(response["message"])
        return response