from flask import Blueprint, request, jsonify
from srf_form import main
import config

srf_bp = Blueprint('srf', __name__)

@srf_bp.route('/submit', methods=['POST'])
def submit_srf():
    # Extract form data
    form_data = request.form.to_dict()
    
    vars =  {
        "vsphere_template": form_data.get("vsphere_template"),
        "location_network": form_data.get("location_network"),
        "static_ip" : form_data.get("static_ip").lower() == "true",
        "ip_address": form_data.get("ip_address"),
        "vm_name": form_data.get("vm_name").upper() 
                    if form_data.get("server_os").lower() == "windows" 
                    else form_data.get("vm_name").lower(),
        "vm_cpus": int(form_data.get("vm_cpus")),
        "vm_memory": int(form_data.get("vm_memory")) * 1024,
        "vm_folder": form_data.get("vm_folder"),
        "additional_disk_sizes": [int(size) 
                                  for size in form_data.get("additional_disk_sizes").split(',')] 
                                    if form_data.get("additional_disk_sizes") 
                                    else [],
        "AD_remarks": form_data.get("AD_remarks"),
        "cada_hostgroups": ["Unix_ADV_Servers_All"] + [group.strip() 
                                                       for group in form_data.get("cada_hostgroups").split(',')] 
                                                        if form_data.get("cada_hostgroups") 
                                                        else ["Unix_ADV_Servers_All"],
        "server_os": form_data.get("server_os"),
        "server_type": form_data.get("server_type"),
        "server_env": form_data.get("server_env"),
        "server_location": form_data.get("server_location"),
        "devhub_app_id": form_data.get("devhub_app_id"),
        "devhub_app_name": form_data.get("devhub_app_name"),
        "awx_url": config.awx_url,
        "email": form_data.get("email")
        }
    if vars:
        response = main(vars)
        # Handle the response
        if response["status"] == "success":
            return jsonify({
                "message": "AWX template launched for VM Deployment.",
                "job_id": response["job_id"],
                "job_url": f"{config.awx_url}/#/jobs/playbook/{response['job_id']}/output",
                "job_stdout": response["job_stdout"]
            }), 200
        elif response["status"] == "error":
            return jsonify({
                "status": "error",
                "message": response["message"]
            }), 400
        else:
            return jsonify({
                "status": "error",
                "message": "Job not triggered. Something went wrong. Please check the app logs."
            }), 500
    else:
        return jsonify({
            "status": "error",
            "message": "Invalid input data. Please check the form data."
        }), 400