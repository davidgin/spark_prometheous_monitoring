#!/bin/bash
gcloud compute instances describe -dataproc-cluster-m --zone=-central1-a \
--format='get(networkInterfaces[0].accessConfigs[0].natIP)'
