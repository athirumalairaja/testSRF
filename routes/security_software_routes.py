from flask import Blueprint, request, jsonify, current_app
import os
from software_form import software_main
from security_patch import security_main
import config
from datetime import datetime

# Create a Blueprint for security software installation
software_bp = Blueprint('security_software_routes', __name__)

@software_bp.route('/submit', methods=['POST'])
def security_software_install():
    try:
        # Get form data
        software = request.form.getlist('software')  # Get list of selected software
        security_patch = request.form.getlist('security-patch')  # Get list of selected patches
        job_slice_count = request.form.get('job_slice_count')  # Get job slice count
        email = request.form.get('email')
        hostnames_input = request.form.get('hostnames')  # Get hostnames from textarea
        job_tags = request.form.getlist('job_tags')
        skip_tags = request.form.getlist('skip_tags')
        skip_cada_roles = request.form.get('skip_cada_roles', 'false').lower() == 'true'
        skip_reboot = request.form.get('skip_reboot', 'false').lower() == 'true'
        
        # Validate that at least one checkbox is selected
        if not software and not security_patch:
            return jsonify({"error": "Please select at least one software or security patch"}), 400

        # Validate job slice count
        if not job_slice_count or not job_slice_count.isdigit() or int(job_slice_count) < 1:
            return jsonify({"error": "Invalid job slice count"}), 400

        # Validate email
        if not email or "@" not in email:
            return jsonify({"error": "Invalid email address"}), 400

        # Process hostnames from textarea
        hostnames = [hostname.strip() for hostname in hostnames_input.split('\n') if hostname.strip()]
        if not hostnames:
            return jsonify({"error": "No hostnames provided"}), 400
        
        
        # Create inventory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        inventory_name = f"PPS-inventory-{timestamp}"
        cada_hostgroups   =  ["Unix_ADV_Servers_All"] 
        
        # Prepare variables for software and security
        software_vars = {
            "apps_to_install": software,
            "job_slice_count": int(job_slice_count),  # Convert to integer
            "hostnames": hostnames,  # List of hostnames from textarea
            "email": email,
            "awx_url": config.awx_url
        }
        
        # Initialize security_vars with default values
        security_vars = {
            "job_slice_count": int(job_slice_count),  # Convert to integer
            "hostnames": hostnames,  # List of hostnames from textarea
            "job_tags": job_tags,  
            "skip_tags": skip_tags,
            "email": email,
            "patching": False,  # Default value
            "harden": False,    # Default value
            "standard": False,   # Default value
            "awx_url": config.awx_url,
            "skip_cada_roles": skip_cada_roles,
            "skip_reboot": skip_reboot,
            "cada_hostgroups": cada_hostgroups,
            "inventory_name": inventory_name
        }
        
        # Update security_vars based on the presence of 'patch', 'harden', 'standard' in security_patch
        if 'patch' in security_patch:
            security_vars['patching'] = True
        if 'harden' in security_patch:
            security_vars['harden'] = True
        if 'standard' in security_patch:
            security_vars['standard'] = True

        # Log the vars variable for debugging
        print(software_vars)
        print(security_vars)

        # Initialize responses
        software_response = None
        security_response = None

        # Call software_main only if apps_to_install has values
        if software:
            software_response = software_main(software_vars)
            # Log the software_response for debugging
            print(f"Software Response: {software_response}")

        # Call security_main only if security_playbook has values
        if security_patch:
            # Trigger security_main regardless of software_main's success or failure
            security_response = security_main(security_vars)
            # Log the security_response for debugging
            print(f"Security Response: {security_response}")

        # Handle the responses
        if (not software or (software_response and software_response["status"] in ["success", "error"])) and \
           (not security_patch or (security_response and security_response["status"] in ["success", "error"])):
            message = "AWX template launched"
            if software:
                message += " for Software Install"
                if software_response["status"] == "error":
                    message += " (failed)"
            if security_patch:
                if software:
                    message += " and"
                message += " for Security Patching"
                if security_response["status"] == "error":
                    message += " (failed)"
            message += "."

            response_data = {
                "message": message,
            }

            if software:
                response_data.update({
                    "software_job_id": software_response["job_id"],
                    "software_job_url": f"{config.awx_url}/#/jobs/playbook/{software_response['job_id']}/output",
                    "software_job_stdout": software_response["job_stdout"],
                    "software_status": software_response["status"]
                })
            if security_patch:
                response_data.update({
                    "security_job_id": security_response["job_id"],
                    "security_job_url": f"{config.awx_url}/#/jobs/playbook/{security_response['job_id']}/output",
                    "security_job_stdout": security_response["job_stdout"],
                    "security_status": security_response["status"]
                })

            return jsonify(response_data), 200
        else:
            # If either of the responses is an error, return the error message
            error_message = ""
            if software and software_response and software_response["status"] == "error":
                error_message += f"Software Error: {software_response['message']} "
            if security_patch and security_response and security_response["status"] == "error":
                error_message += f"Security Error: {security_response['message']} "
            
            return jsonify({
                "status": "error",
                "message": error_message.strip()
            }), 400

    except Exception as e:
        print(f"Error in security_software_install route: {e}")
        return jsonify({
            "status": "error",
            "message": "An internal server error occurred. Please check the logs."
        }), 500