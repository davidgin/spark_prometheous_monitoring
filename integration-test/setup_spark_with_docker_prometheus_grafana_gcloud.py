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

    print("Reading and preparing prometheus.yml...")
    prometheus_yml = read_file("prometheus.yml")
    prometheus_yml = prometheus_yml.replace("gcp-project-id", config['gcp_project']) \
                                   .replace("us-central1-a", config['zone']) \
                                   .replace("dataproc-cluster", config['cluster_name'])
    with open("prometheus.yml", "w") as f:
        f.write(prometheus_yml)

    print("Uploading prometheus.yml to GCS...")
    run_command(f"gcloud storage cp prometheus.yml gs://{config['gcs_bucket']}/prometheus.yml")

    print("Uploading docker-compose.yml to GCS...")
    run_command(f"gcloud storage cp docker-compose.yml gs://{config['gcs_bucket']}/binaries/docker-compose.yml")

    print("Detecting Spark UI port...")
    master_ip = run_command(f"gcloud compute instances describe {config['cluster_name']}-m --zone={config['zone']} --format='get(networkInterfaces[0].accessConfigs[0].natIP)'")
    spark_port = get_spark_ui_port(master_ip)
    print(f"Detected Spark UI port: {spark_port}")

    print("Fetching worker node names (computed once)...")
    worker_nodes = run_command(f"gcloud compute instances list --filter='name:{config['cluster_name']}-w-' --format='value(name)'").splitlines()
    print(f"Found worker nodes: {worker_nodes}")

    print("Configuring Spark and setting up Prometheus/Grafana on master...")
    master_cmd = f"""
sudo gsutil cp gs://{config['gcs_bucket']}/metrics.properties /etc/spark/conf/metrics.properties
echo 'spark.ui.prometheus.enabled true' | sudo tee -a /etc/spark/conf/spark-defaults.conf
echo 'spark.sql.streaming.metricsEnabled true' | sudo tee -a /etc/spark/conf/spark-defaults.conf
echo 'spark.metrics.conf /etc/spark/conf/metrics.properties' | sudo tee -a /etc/spark/conf/spark-defaults.conf
if ! command -v docker &> /dev/null; then
  sudo apt-get update
  sudo apt-get install -y docker.io
  sudo systemctl start docker
  sudo systemctl enable docker
fi
if ! command -v docker-compose &> /dev/null; then
  sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
fi
sudo mkdir -p /home/$(whoami)/monitoring
sudo gsutil cp gs://{config['gcs_bucket']}/binaries/docker-compose.yml /home/$(whoami)/monitoring/docker-compose.yml
sudo gsutil cp gs://{config['gcs_bucket']}/prometheus.yml /home/$(whoami)/monitoring/prometheus.yml
sudo sed -i 's/localhost:4040/localhost:{spark_port}/g' /home/$(whoami)/monitoring/prometheus.yml
cd /home/$(whoami)/monitoring
sudo docker-compose down 2>/dev/null || true
sudo docker-compose up -d
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

    print("Configuring firewall rules...")
    run_command(f"gcloud compute firewall-rules create allow-monitoring --allow tcp:9090,tcp:3000 --target-tags=dataproc-{config['cluster_name']} --description='Allow Prometheus and Grafana access'", check=False)

    print(f"Setup complete! Check http://{master_ip}:9090 for Prometheus and http://{master_ip}:3000 for Grafana.")

if __name__ == "__main__":
    main()
