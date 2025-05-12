import os
awx_url = os.environ.get("AWX_URL")
username = os.environ.get("AWX_USERNAME")
password = os.environ.get("AWX_PASSWORD")
api_url = f"{awx_url}/api/v2/"

#SRF
srf_project_name    =  'Project_VM Deploy'
srf_inventory_name  =   'localhost'
srf_organizations   =   'Infrastructure'
srf_eename          =   'EE_VM Build'

srf_credentials   =   ['efv-ansible', 'HashiCorp Vault AppRole client token - AIM']
srf_playbook        =   'main.yaml'


#VM-Decommission
decomm_project_name    =  'project-vm-decomm'
decomm_inventory_name  =   'Windows'
decomm_organizations   =   'Infrastructure'
decomm_eename          =   'EE_VM Build'

decomm_credentials   =   ['svc-efvansible', 'HashiCorp Vault AppRole client token - AIM']
decomm_playbook        =   'main.yaml'

#Software-Install
software_project_name   = 'Project-Software-Install'
software_inventory_name = 'software-inventory'
software_organizations  = 'Infrastructure'
software_eename         = 'EE_PPS'
software_credentials    =   ['efv-ansible', 'HashiCorp Vault AppRole client token - AIM']
software_playbook       =   'main.yaml'

#Security-Patch
security_project_name   = 'Project_PPS'
security_inventory_name = 'PPS_inventory'
security_organizations  = 'Infrastructure'
security_eename         = 'EE_PPS'
security_credentials    =   ['efv-ansible', 'HashiCorp Vault AppRole client token - AIM']
security_playbook       =   'security_patching.yaml'

LOGGING_LEVEL = "DEBUG"

receivers = ["adalvi228@cable.comcast.com"]
smtp_host = "mailrelay.comcast.com"
smtp_port = 25


# For UI
# secret_key = os.environ.get("SECRET_KEY")
# login_username = os.environ.get("USERNAME")
# login_password = os.environ.get("PASSWORD")