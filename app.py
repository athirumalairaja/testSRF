import json
import os
import csv
from flask import Flask, render_template, jsonify
from routes.decomm_routes import decomm_bp
from routes.srf_routes import srf_bp
from routes.security_software_routes import software_bp
from collections import defaultdict

app = Flask(__name__)

# Get the absolute path to the directory containing this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

templates_path = os.path.join(BASE_DIR, 'data', 'templates.json')
networks_path = os.path.join(BASE_DIR, 'data', 'networks.csv')
# Load networks data from CSV
def load_networks_data():
    networks = []
    with open(networks_path, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            networks.append(row)
    return networks

# Load templates data from JSON
def load_templates_data():
    with open(templates_path, 'r') as f:
        return json.load(f)

# Route for the home page
@app.route('/infra-auto')
def home():
    return render_template('infrastructure-automation.html')

# Route for the SRF form
@app.route('/infra-auto/srf')
def srf():
    return render_template('srf-form.html')

# Route for the VM Decommission form
@app.route('/infra-auto/vm-decommission')
def vm_decommission():
    return render_template('decomm-form.html')

@app.route('/infra-auto/security_software_install')
def security_software_install():
    return render_template('security_software_install_form.html')

# API endpoint to get locations
@app.route('/infra-auto/api/locations')
def get_locations():
    networks = load_networks_data()
    locations = sorted(list(set(net['Location'] for net in networks)))
    return jsonify(locations)

# API endpoint to get vCenters for a location
@app.route('/infra-auto/api/vcenters/<location>')
def get_vcenters(location):
    networks = load_networks_data()
    vcenters = sorted(list(set(net['vCenter'] for net in networks if net['Location'] == location)))
    return jsonify(vcenters)

# API endpoint to get data centers for a vCenter
@app.route('/infra-auto/api/datacenters/<vcenter>')
def get_datacenters(vcenter):
    networks = load_networks_data()
    datacenters = sorted(list(set(net['Data_Center'] for net in networks if net['vCenter'] == vcenter)))
    return jsonify(datacenters)

# API endpoint to get clusters for a data center
@app.route('/infra-auto/api/clusters/<datacenter>')
def get_clusters(datacenter):
    networks = load_networks_data()
    clusters = sorted(list(set(net['vsphere_cluster'] for net in networks if net['Data_Center'] == datacenter)))
    return jsonify(clusters)

# API endpoint to get datastores for a cluster
@app.route('/infra-auto/api/datastores/<cluster>')
def get_datastores(cluster):
    networks = load_networks_data()
    datastores = sorted(list(set(net['Data_store'] for net in networks if net['vsphere_cluster'] == cluster)))
    return jsonify(datastores)

# API endpoint to get networks for a datastore
@app.route('/infra-auto/api/networks/<datastore>')
def get_networks(datastore):
    networks = load_networks_data()
    network_options = [{
        'value': net['Location_Network'],
        'display': f"{net['Location_Network']} - ({net['IP_Range']})"
    } for net in networks if net['Data_store'] == datastore]
    return jsonify(network_options)

# API endpoint to get templates by OS type
@app.route('/infra-auto/api/templates/<os_type>')
def get_templates(os_type):
    templates = load_templates_data()
    return jsonify(templates.get(os_type.lower(), []))

# Register Blueprints
app.register_blueprint(decomm_bp, url_prefix='/infra-auto/vm-decommission')
app.register_blueprint(srf_bp, url_prefix='/infra-auto/srf')
app.register_blueprint(software_bp, url_prefix='/infra-auto/security_software_install')

if __name__ == '__main__':
    app.run(host = '0.0.0.0', port=5004)