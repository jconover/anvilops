#!/bin/bash

# AnvilOps Frontend
kubectl port-forward -n anvilops svc/anvilops-frontend 3000:80 &

# AnvilOps API (Swagger at /docs)
kubectl port-forward -n anvilops svc/anvilops-api 8000:80 &

# AWX (Ansible Tower)
kubectl port-forward -n awx svc/awx-service 8052:80 &
