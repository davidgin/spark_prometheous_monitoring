#!/usr/bin/env python3

import os
import subprocess
import sys
import requests
import json
import configparser

def load_config(config_file="config.ini"):
    config = configparser.ConfigParser()
    if not os.path.exists(config_file):
        print(f"Error: Config file '{config_file}' not found.")
        sys.exit(1)
    config.read(config_file)
    if 'Dataproc' not in config:
        print("Error: 'Dataproc' section missing in config file.")
        sys.exit(1)
    return config['Dataproc']

def run_command(command, check=True):
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

def read_file(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    with open(file_path, "r") as f:
        return f.read()

def get_spark_ui_port(master_ip):
    try:
        response = requests.get(f"http://{master_ip}:8080/json/", timeout=5)
        response.raise_for_status()
        data = response.json()
        for app in data.get("activeapps", []):
            if "spark" in app.get("name", "").lower():
                return str(app.get("uiport", "4040"))
        return "4040"
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"Error fetching Spark UI port: {e}. Defaulting to 4040.")
        return "4040"

def main():
    global config
    config = load_config()

    print("Reading metrics.properties...")
    metrics_properties = read_file("metrics.properties")
    with open("metrics.properties", "w") as f:
        f.write(metrics_properties)

    print("Uploading metrics.properties to GCS...")
    run_command(f"gcloud storage cp metrics.properties gs://{config['gcs_bucket']}/metrics.properties")

    print("Detecting Spark UI port...")
    master_ip = run_command(f"gcloud compute instances describe {config['cluster_name']}-m --zone={config['zone']} --format='get(networkInterfaces[0].accessConfigs[0].natIP)'")
    spark_port = get_spark_ui_port(master_ip)
    print(f"Detected Spark UI port: {spark_port}")

    print("Fetching worker node names (computed once)...")
    worker_nodes = run_command(f"gcloud compute instances list --filter='name:{config['cluster_name']}-w-' --format='value(name)'").splitlines()
    print(f"Found worker nodes: {worker_nodes}")

    print("Reading and updating prometheus.yml...")
    prometheus_yml = read_file("prometheus.yml")
    prometheus_yml = prometheus_yml.replace("-gcp-project-id", config['gcp_project']) \
                                   .replace("us-central1-a", config['zone']) \
                                   .replace("-dataproc-cluster", config['cluster_name']) \
                                   .replace("4040", spark_port)
    with open("prometheus.yml", "w") as f:
        f.write(prometheus_yml)

    print("Configuring Spark and updating Prometheus on master...")
    master_cmd = f"""
sudo gsutil cp gs://{config['gcs_bucket']}/metrics.properties /etc/spark/conf/metrics.properties
echo 'spark.ui.prometheus.enabled true' | sudo tee -a /etc/spark/conf/spark-defaults.conf
echo 'spark.sql.streaming.metricsEnabled true' | sudo tee -a /etc/spark/conf/spark-defaults.conf
echo 'spark.metrics.conf /etc/spark/conf/metrics.properties' | sudo tee -a /etc/spark/conf/spark-defaults.conf
if [ -f /home/$(whoami)/prometheus.yml ]; then
  echo 'Updating existing prometheus.yml...'
  cat << 'EOF' > /home/$(whoami)/prometheus.yml
{prometheus_yml}
EOF
  pkill -f prometheus || echo 'Prometheus not running, please restart it manually'
else
  echo 'prometheus.yml not found, skipping update.'
fi
"""
    run_command(f"gcloud compute ssh {config['cluster_name']}-m --zone={config['zone']} --command='{master_cmd}'")

    print("Configuring Spark on worker nodes...")
    worker_cmd = f"""
sudo gsutil cp gs://{config['gcs_bucket']}/metrics.properties /etc/spark/conf/metrics.properties
echo 'spark.ui.prometheus.enabled true' | sudo tee -a /etc/spark/conf/spark-defaults.conf
echo 'spark.sql.streaming.metricsEnabled true' | sudo tee -a /etc/spark/conf/spark-defaults.conf
echo 'spark.metrics.conf /etc/spark/conf/metrics.properties' | sudo tee -a /etc/spark/conf/spark-defaults.conf
"""
    for worker in worker_nodes:
        print(f"Configuring worker node: {worker}")
        run_command(f"gcloud compute ssh {worker} --zone={config['zone']} --command='{worker_cmd}'")

    print(f"Update complete! Check http://{master_ip}:9090 for Prometheus.")

if __name__ == "__main__":
    main()
