# Dataproc Monitoring with gcloud

![Dataproc Logo](https://cloud.google.com/static/dataproc/images/dataproc-logo.svg)  
*Monitor your Google Cloud Dataproc Spark cluster with Prometheus and Grafana using gcloud-based scripts.*

## Overview

This repository provides two Python scripts to configure monitoring for an existing Google Cloud Dataproc Spark cluster using only `gcloud` commands. Initially explored as a Terraform-based solution, the project evolved into a lightweight, Python-driven approach that sets up Spark metrics, deploys Prometheus and Grafana (optionally), and leverages Prometheus' GCP service discovery with lifecycle relabeling for dynamic worker node monitoring. Key features include:

- **One-Time Execution**: Scripts run once and exit, avoiding continuous running as per user preference.
- **Dynamic Spark UI Port Detection**: Automatically detects the active Spark UI port.
- **Lifecycle Relabeling**: Labels worker nodes as `spot` or `on-demand` in Prometheus without ongoing script intervention.
- **gcloud-Only Approach**: Avoids Google Cloud SDK Python libraries, using CLI commands exclusively.

## Project Structure
```
├── alert_rules.yml
├── config.ini
├── docker-compose.yml
├── DockerFile
├── metrics.properties
├── metrics_table_sorted_by_importance
├── prometheus.yml
├── README.md
├── requirements.txt
├── run-manually.txt
├── setup_spark_with_docker_prometheus_grafana_gcloud.py
├── spark_metrics.xlsx
├── submit_job.template.txt
├── update_existing_spark_prometheus_grafana_gcloud.py
└── verification.sh
 
```


## Background

This project aims to automate monitoring and alretinng confuguratioin on a DataProc cluster with sopt instancess 
for  spark structured streaming jobs. It highlights a preference for script-based, one-time execution over infrastructure-as-code complexity, while retaining core functionality like Spark metrics and monitoring setup.
It can be transormed to a Terraform project.

## Features

### 1. One-Time Setup Scripts
- Both scripts execute once to configure the cluster and exit, respecting your desire to avoid continuous running.

### 2. Master IP Retrieval
- Uses `gcloud compute instances describe <cluster_name>-m` to fetch the master VM’s public IP dynamically.

### 3. Worker Nodes Computed Once
- Worker nodes are listed once using `gcloud compute instances list --filter='name:<cluster_name>-w-'` and iterated over, matching the original Python approach.

### 4. Dynamic Spark UI Port Detection
- Queries `http://<master_ip>:8080/json/` to detect the active Spark UI port, defaulting to `4040` if unavailable.

### 5. Lifecycle Relabeling in Prometheus
- Reintroduced `spot` and `on-demand` labels in `prometheus.yml`, enabling Prometheus to dynamically label workers without script re-execution.

### 6. gcloud-Only Dependency
- Relies solely on `gcloud` commands (e.g., `gcloud storage cp`, `gcloud compute ssh`), avoiding SDK libraries.

### 7. External Configuration Files
- `metrics.properties` and `prometheus.yml` are separate files, uploaded to GCS and applied to nodes.

### 8. Idempotent Configuration
- Uses `tee -a` with checks to append Spark config lines only if missing, ensuring safe re-runs.

### 9. Docker-Based Monitoring
- `setup_spark_with_docker_prometheus_grafana_gcloud.py` installs Docker and deploys Prometheus/Grafana on the master node.

### 10. Firewall Rule Setup
- Adds a firewall rule (`allow-monitoring`) for ports `9090` (Prometheus) and `3000` (Grafana).

## Prerequisites

- **Google Cloud SDK**: Installed and authenticated (`gcloud auth login` or service account key).
- **Python 3.6+**: With the `requests` library (`pip3 install requests`).
- **Existing Dataproc Cluster**: Running in GCP with SSH access enabled.
- **GCS Bucket**: For storing configuration files.
- **Network Access**: Master VM must have a public IP (or adjust for internal IPs).

## Installation

1. **Clone or Download**:
2. unzip dataproc_monitoring_gcloud.zip
3. cd dataproc_monitoring_gcloud

 **Install Dependencies**:
   pip3 install requests
   
   **Make Scripts Executable** (optional): 
   ```` chmod +x *.py  ```` 

 ## Configuration

Edit `config.ini` with your GCP details:
## Configuration

Edit `config.ini` with your GCP details:

```` [Dataproc]
gcp_project = your-gcp-project-id
zone = us-central1-a
cluster_name = my-dataproc-cluster
gcs_bucket = my-bucket````


- **`gcp_project`**: Your GCP project ID./ or use secretes stored in gcp secret manager
- **`zone`**: Zone of your Dataproc cluster (e.g., `us-central1-a`).
- **`cluster_name`**: Name of your existing Dataproc cluster.
- **`gcs_bucket`**: GCS bucket for config files.

## Usage

### Setup Prometheus and Grafana

````
./setup_spark_with_docker_prometheus_grafana_gcloud.py

- Configures Spark metrics on all nodes.
- Installs Docker and Docker Compose on the master.
- Deploys Prometheus and Grafana via Docker Compose.
- Creates a firewall rule for access.

**Output**: URLs for Prometheus (`http://<master_ip>:9090`) and Grafana (`http://<master_ip>:3000`).

## Verification

- **Spark Config**:
  gcloud compute ssh <cluster_name>-m --zone= <zone> --command="cat /etc/spark/conf/spark-defaults.conf"
  - **Prometheus**:
- Visit `http://<master_ip>:9090/targets` to see Spark targets.
- **Grafana**:
- Access `http://<master_ip>:3000` and add Prometheus as a data source.

## Build image if running from k8 

To use:

    Build the image: docker build -t imageName .
    Run for setup: docker run -v /var/run/docker.sock:/var/run/docker.sock -it myimage
    Run for update: docker run -v /var/run/docker.sock:/var/run/docker.sock -it myimage update_existing_spark_prometheus_grafana_gcloud.py

This setup ensures both entry points are supported, with the default being the setup script, and users can switch by specifying the update script at runtime. The approach is flexible, acknowledging the complexity of Docker interactions and potential script dependencies.

## Pros and Cons of Using gcloud vs. Google Cloud SDK

### Why gcloud?
These scripts use `gcloud` commands instead of the Google Cloud SDK Python libraries (e.g., `google-cloud-storage`, `google-cloud-compute`). Here’s why this choice was made and its trade-offs:

#### Pros
- **Simplicity**: No need to install additional Python packages beyond `requests`, reducing dependency management.
- **Ubiquity**: `gcloud` is widely installed and familiar to GCP users, leveraging existing CLI authentication.
- **Portability**: Runs on any system with `gcloud` installed, no Python-specific SDK setup required.
- **Transparency**: Commands are human-readable and can be tested manually (e.g., `gcloud compute instances describe`).
- **Lightweight**: Avoids the overhead of SDK imports and initialization, keeping scripts lean.

#### Cons
- **Performance**: Shelling out to `gcloud` via `subprocess.run` is slower than direct API calls with the SDK.
- **Error Handling**: Parsing `gcloud` output is less robust than SDK exceptions (e.g., relies on string manipulation).
- **Flexibility**: Limited to `gcloud`’s CLI capabilities; SDK offers finer-grained control (e.g., batch operations).
- **Dependencies**: Assumes `gcloud` is installed and configured, which might not always be true in all environments.
- **Complexity in Scripting**: Multiline SSH commands (e.g., via `gcloud compute ssh`) are harder to maintain than SDK method calls.

**Conclusion**: The `gcloud`-only approach prioritizes simplicity and accessibility over performance and programmatic control, suitable for one-time setup tasks like this project.

## Key Technical Details


### 12. Transition to Python
- Shifted to Python scripts for a simpler, script-based approach over bash scripts.

### 13. Master IP Detection
- Uses `gcloud compute instances describe` to get `networkInterfaces[0].accessConfigs[0].natIP`.

### 14. Worker Node Iteration
- Fetches workers once with `gcloud compute instances list` and loops over them for configuration.

### 15. Spark Metrics
- `metrics.properties` enables Prometheus and CSV sinks for Spark metrics.

### 16. Prometheus Configuration
- `prometheus.yml` uses `gcp_sd_configs` for dynamic worker discovery and lifecycle relabeling. Critical for spott instances.

### 17. Docker Deployment
- Installs Docker and Docker Compose on the master if absent, runs Prometheus/Grafana in containers.

### 18. Port Handling
- Dynamically replaces `4040` in `prometheus.yml` with the detected Spark UI port.

### 19. GCS Integration
- Uploads config files to GCS using `gcloud storage cp`.

### 20. SSH Execution
- Uses `gcloud compute ssh` to run commands on master and worker nodes.

### 21. Firewall Rules
- Non-fatal firewall creation (`check=False`) to avoid errors if rules exist.

### 22. No Continuous Execution
- Scripts run once; Prometheus’ service discovery handles ongoing monitoring.

### 24. Dynamic Worker Discovery
- Lifecycle relabeling in Prometheus eliminates the need for repeated script runs to update worker states.

### 25. Idempotency in Python
- Python scripts mimic Terraform’s idempotent config updates using conditional appends.

### 26. External File Management
- Separate `metrics.properties` and `prometheus.yml` mirror Terraform’s approach, uploaded via `gcloud`.

### 27. Spark Port Detection Logic
- Python’s `get_spark_ui_port` replicates Terraform’s `curl`-based port detection.

### 28. Firewall Rule Creation
- Python adds firewall rules like Terraform’s `google_compute_firewall`.

### 29. Output URLs
- Scripts print Prometheus/Grafana URLs, similar to Terraform outputs.

### 30. Date Context
- Built with knowledge as of March 10, 2025, reflecting continuous updates.

## Troubleshooting

- **No Master IP**: Ensure the cluster exists and has a public IP (`natIP`).
- **SSH Errors**: Verify `gcloud` authentication and Compute Engine permissions.
- **Port Detection Fails**: Check if Spark is running; defaults to `4040`.
- **Prometheus Not Scraping**: Confirm firewall rules and correct Spark port in `prometheus.yml`.


## License

This project is unlicensed—use it freely as you see fit.

