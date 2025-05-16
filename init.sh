#!/bin/bash

if pip install -r requirements.txt; then
    if chmod +x verification.sh; then
        if python setup_spark_with_docker_promethus_grafana_gcloud.py; then
            echo "Success in setup_spark_with_docker_promethus_grafana_gcloud"
        else
            echo "Failure: setup_spark_with_docker_promethus_grafana_gcloud"
            exit 1
        fi
    else
        echo "Failure: chmod failed"
        exit 1
    fi
else
    echo "Failure: pip install failed"
    exit 1
fi
