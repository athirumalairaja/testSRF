from flask import Blueprint, request, jsonify
from decomm_form import main
import config

decomm_bp = Blueprint('vm-decommission', __name__)

@decomm_bp.route('/submit', methods=['POST'])
def submit_decomm():
    # Extract form data
    form_data = request.form.to_dict()
    
    # Process form data
    vars = {
        "vm_name": form_data.get("vm_name"),
        "email": form_data.get("email"),
        "awx_url": "https://efvawx-qa.ecp.comcast.com"
    }
    
    # Extract the list of VM names from the string
    if "vm_name:" in vars["vm_name"]:
         # Remove the "vm_name:" prefix and strip whitespace
         vm_names_str = vars["vm_name"].split("vm_name:")[1].strip()
         # Convert the string to a list of VM names
         vm_names = [name.strip() for name in vm_names_str.strip("[]").split(",")]
         # Update the vars dictionary with the list of VM names
         vars["vm_name"] = vm_names
     
     # Print or process the vars dictionary (for debugging or further processing)
    print(vars)
    
    if vars:
         # Call the main function and get the response dictionary
        response = main(vars)
        
        # Handle the response
        if response["status"] == "success":
            return jsonify({
                "message": "AWX template launched for VM Decommission.",
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