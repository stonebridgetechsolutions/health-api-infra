# Runbook — Health API

## Deploy

### Automated (CI/CD)

Push to `main` triggers the full pipeline. Production requires manual approval in the GitHub Actions `production` environment.

### Manual Deploy

```bash
# Authenticate
gcloud auth login
gcloud container clusters get-credentials health-api-cluster --region us-central1

# Deploy to staging
helm upgrade --install health-api ./helm/health-api \
  -n staging --create-namespace \
  -f ./helm/health-api/values-staging.yaml \
  --set image.repository=us-central1-docker.pkg.dev/PROJECT_ID/health-api-repo/health-api \
  --set image.tag=IMAGE_TAG \
  --wait --timeout 5m

# Deploy to production
helm upgrade --install health-api ./helm/health-api \
  -n production --create-namespace \
  -f ./helm/health-api/values-prod.yaml \
  --set image.repository=us-central1-docker.pkg.dev/PROJECT_ID/health-api-repo/health-api \
  --set image.tag=IMAGE_TAG \
  --wait --timeout 5m
```

## Rollback

### Helm Rollback

```bash
# List release history
helm history health-api -n production

# Rollback to previous revision
helm rollback health-api -n production

# Rollback to specific revision
helm rollback health-api 3 -n production
```

### Rollback to Specific Image

```bash
helm upgrade --install health-api ./helm/health-api \
  -n production \
  -f ./helm/health-api/values-prod.yaml \
  --set image.repository=us-central1-docker.pkg.dev/PROJECT_ID/health-api-repo/health-api \
  --set image.tag=KNOWN_GOOD_SHA \
  --wait --timeout 5m
```

## Verify Deployment

```bash
# Check pod status
kubectl get pods -n production -l app.kubernetes.io/name=health-api

# Check endpoints
kubectl port-forward svc/health-api 8080:80 -n production
curl http://localhost:8080/health
curl http://localhost:8080/ready

# Check HPA
kubectl get hpa -n production

# View logs
kubectl logs -l app.kubernetes.io/name=health-api -n production --tail=100
```

## Troubleshooting

### Pods not starting

```bash
kubectl describe pod -l app.kubernetes.io/name=health-api -n production
kubectl get events -n production --sort-by='.lastTimestamp'
```

### Image pull errors

Verify Artifact Registry access:
```bash
gcloud artifacts repositories describe health-api-repo --location=us-central1
```

### Terraform state issues

```bash
cd terraform
terraform refresh -var="project_id=PROJECT_ID"
terraform plan -var="project_id=PROJECT_ID"
```

## Infrastructure Teardown

```bash
# Remove Helm releases
helm uninstall health-api -n staging
helm uninstall health-api -n production

# Destroy Terraform resources
cd terraform
terraform destroy -var="project_id=PROJECT_ID"
```
