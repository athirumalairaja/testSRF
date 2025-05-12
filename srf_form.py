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
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s') #- [Line %(lineno)d]
    console_handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(console_handler)

def check_job_status(job_id, receivers):
    url = f"{config.api_url}jobs/{job_id}/"
    stdout_url = f"{config.api_url}jobs/{job_id}/stdout/?format=txt"  # URL to fetch job stdout

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
                # Extract the last failed task output
                failed_lines = [line for line in job_stdout.splitlines() if "FAILED!" in line or "fatal:" in line.lower()]
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
            return job_status, job_stdout

        time.sleep(10)  # Wait for 10 seconds before polling again

#Search project and return its id
def return_project_id():
    url = config.api_url + 'projects/'
    response = requests.get(f'{url}?name={config.srf_project_name}', auth=(config.username, config.password), verify=False)

    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")
    if response.status_code != requests.codes.ok:
        raise ObjectNotFound(f"{response.status_code} - Failed to search project: name={config.srf_project_name}")

    search_response = response.json()
    if not search_response['count']:
        raise ObjectNotFound(f"{response.status_code} - Project doesn't exist: name={config.srf_project_name}")
    else:
        project_id = search_response['results'][0]['id']

    logging.info(f'{response.status_code} - Found project: name={config.srf_project_name}, id={project_id}')
    return project_id


#Search inventory and return its id
def return_inventory_id():
    url = config.api_url + 'inventories/'
    response = requests.get(f'{url}?name={config.srf_inventory_name}', auth=(config.username, config.password), verify=False)

    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")
    if (response.status_code != requests.codes.ok):
        raise ObjectNotFound(f"{response.status_code} - Failed to search inventory: name={config.srf_inventory_name}")

    search_response = response.json()

    if not search_response['count']:
        raise ObjectNotFound(f"{response.status_code} - Inventory doesn't exist: name={config.srf_inventory_name}")
    else:
        inventory_id = search_response['results'][0]['id']

    logging.info(f'{response.status_code} - Foun inventory: name={config.srf_inventory_name}, id={inventory_id}')
    return inventory_id


#Search credential and return its id
def return_credential_id(credential):
    url = config.api_url + 'credentials/'
    response = requests.get(f"{url}?name={credential}", auth=(config.username, config.password), verify=False)
    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")

    if (response.status_code != requests.codes.ok):
        raise ObjectNotFound(f"{response.status_code} - Failed to search credential: name={credential}")

    search_response = json.loads(response.text)
    count = search_response['count']

    if not count:
        raise ObjectNotFound(f"{response.status_code} - credential not found: name={credential}")
    elif search_response['count'] > 1:
        raise TooManyResults(f"{response.status_code} - TooMany credentials found: name={credential} count={search_response['count']}")
    else:
        credential_id = search_response['results'][0]['id']

    logging.info(f"{response.status_code} - Found Credential: name={credential}, id={credential_id}")
    return credential_id


#Search ee and return its id
def get_ee_id():
    url = config.api_url + 'execution_environments/'
    response = requests.get(f'{url}?name={config.srf_eename}', auth=(config.username, config.password), verify=False)
    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")

    if response.status_code != 200:
        error_message = response.json()
        logging.error(f'{response.status_code} - Error fetching EE id: name={config.srf_eename}, msg={error_message}')
        return None

    results = response.json().get('results', [])
    if not results:
        logging.error(f'{response.status_code} - EE not found: name {config.srf_eename}, msg: {response.json()}')
        return None

    ee_id = results[0]["id"]
    logging.info(f'{response.status_code} - Found Execution Environment: name={config.srf_eename}, id={ee_id}')
    return ee_id


#Add job_template
def add_job_template(payload, name, temp_credentials, credentials):
    url = config.api_url + 'job_templates/'
    
    response = requests.post(url, auth=(config.username, config.password), verify=False, json=payload)
    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")
    if (response.status_code != 201):
        if response.status_code == 400 and "already exists" in response.text:
            logging.info(f"{response.status_code} - Job Template already exist, name={name}")
            logging.info("updating existing template")
            #updating Existing template
            find_template_id = requests.get(f'{url}?name={name}', auth=(config.username, config.password), verify=False)
            results = find_template_id.json().get('results', [])
            job_template_id = results[0]["id"]
            response = requests.put(f'{url}{job_template_id}/', auth=(config.username, config.password), verify=False, json=payload)
            logging.debug(f"{response.status_code} - {response.url} - template updated successfully")
            return job_template_id
        if response.status_code == 400 and "Playbook not found for project" in response.text:
            raise ActionFailure(f"{response.status_code} - Failed to add job template: name={name}, msg='Playbook not found for project'")
    response_txt = json.loads(response.text)

    job_template_id = response_txt['id']
    # attach credentails to job template
    if temp_credentials:
        url = f"{url}{job_template_id}/credentials/"
        for cred_id in temp_credentials:
            payload = {'id':cred_id}
            response = requests.post(url,auth=(config.username, config.password), verify=False, json=payload)
            logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")
            if (response.status_code != 204):
                raise ActionFailure(f"{response.status_code} - Failed to attach credntial to job template: template_name={name}, cred_id={cred_id} msg={response.text}")
        logging.info(f"{response.status_code} - credentials attached to job template: template_name={name}, credentails={credentials}")
        logging.debug("200 - All credentials attached to job template")  
    logging.info(f"{response.status_code} - Job template created: name={name}, id={job_template_id}")
    return job_template_id


# run created Job template
def run_job_template(job_template_id, name):
    url = f"{config.api_url}job_templates/{job_template_id}/launch/"

    response = requests.post(url, auth=(config.username, config.password), verify=False)
    print(response)
    logging.debug(f"{response.request.method} - {response.status_code} - {response.url}")

    if (response.status_code != 201):
        raise ActionFailure(f"{response.status_code} - Failed to launch Job Template: template_name={name}")
    elif (response.status_code == 401):
        raise ActionFailure(f"{response.status_code} - Failed to launch Job Template: msg={response.json()}")
    job_id = response.json()['job']
    job_stdout =  response.json()['related']['stdout']
    logging.info(f"{response.status_code} - Job launched sucessfully: template_name={name}, job id={job_id}")
    return job_id, job_stdout

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

def main(vars):
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
        project_id = return_project_id()     # getting project ID
        inventory_id= return_inventory_id()      # getting inventory ID
        temp_credentials = []
        playbook = config.srf_playbook

        credentials =   config.srf_credentials    # getting credentials ID
        if credentials:
            for credential in credentials:
                get_credential_id = return_credential_id(credential)
                temp_credentials.append(get_credential_id)
        else:
                logging.info('200 - No credentials mentioned in config')

        ee_id = get_ee_id()       # getting execution environment's ID

        # Extract email from the vars dictionary
        email = vars["email"]
        # Convert email to a list for the receivers parameter
        receivers = [email]

        # payload for creating job template create
        name = f"{vars['server_os']}_build-{vars['vm_name']}"
        payload = {'name': name,
            'description':'created by SRF automation',
            'job_type':'run',
            'inventory':inventory_id,
            'project':project_id,
            'playbook':playbook,
            'execution_environment': ee_id,
            'verbosity':2,
            'extra_vars': json.dumps(vars),
            'job_tags':'',
            'skip_tags':'',
            'become_enabled':''}

        # create job template
        job_template_id = add_job_template(payload,name, temp_credentials, credentials)
        
        if type(job_template_id) == int:
            # Check if a job with the same name is already running
            if is_job_running_with_same_name(name):
                raise ActionFailure(f"A job with the same name '{name}' is already running. Please wait for it to complete.")

            job_id, job_stdout = run_job_template(job_template_id, name)
            
            # Run check_job_status in a separate thread
            job_thread = threading.Thread(target=check_job_status, args=(job_id, receivers))
            job_thread.start()  # Start the thread
            
            # Update response with success details
            response.update({
                "status": "success",
                "job_id": job_id,
                "job_stdout": job_stdout,
                "name": name,
                "message": "Job launched successfully."
            })

        elif type(job_template_id) != int and "already exists" in job_template_id:
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