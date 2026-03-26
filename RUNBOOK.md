# Runbook — Health API

## Deploy

### Automated (CI/CD)

Push to `main` triggers the full pipeline. Production requires manual approval in the GitHub Actions `production` environment.

Pipeline stages:
1. **Lint + Test** — flake8, pytest (10 tests)
2. **Security Scan** — Trivy filesystem scan for CRITICAL vulnerabilities
3. **Build & Push** — Multi-stage Docker build with layer caching, push to Artifact Registry
4. **Deploy Staging** — Helm upgrade with staging values, fetches DB creds from Secret Manager
5. **Deploy Production** — Manual approval gate, then Helm upgrade with prod values

### Manual Deploy

```bash
gcloud container clusters get-credentials health-api-cluster --region us-central1

# Fetch DB credentials
DB_HOST=$(gcloud secrets versions access latest --secret=db-host)
DB_PASSWORD=$(gcloud secrets versions access latest --secret=db-password)

# Deploy
helm upgrade --install health-api ./helm/health-api \
  -n production --create-namespace \
  -f ./helm/health-api/values-prod.yaml \
  --set image.repository=us-central1-docker.pkg.dev/PROJECT_ID/health-api-repo/health-api \
  --set image.tag=IMAGE_TAG \
  --set database.host=$DB_HOST \
  --set database.password=$DB_PASSWORD \
  --wait --timeout 5m
```

## Rollback

```bash
# List release history
helm history health-api -n production

# Rollback to previous revision
helm rollback health-api -n production

# Rollback to specific revision
helm rollback health-api 3 -n production
```

## Verify Deployment

```bash
# Check pods
kubectl get pods -n production

# Check services and external IP
kubectl get svc health-api -n production

# Hit endpoints
EXTERNAL_IP=$(kubectl get svc health-api -n production -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://$EXTERNAL_IP/health
curl http://$EXTERNAL_IP/ready

# Create a pipeline run
curl -X POST http://$EXTERNAL_IP/api/runs -H 'Content-Type: application/json' -d '{"sample_id": "SAMPLE-001"}'

# List runs
curl http://$EXTERNAL_IP/api/runs

# Check Prometheus metrics
curl http://$EXTERNAL_IP/metrics

# Check autoscaling
kubectl get hpa -n production

# Check pod disruption budget
kubectl get pdb -n production

# Check resource quotas
kubectl get resourcequota -n production

# View logs
kubectl logs -l app.kubernetes.io/name=health-api -n production --tail=50
```

## Troubleshooting

### Pods not starting

```bash
kubectl describe pod -l app.kubernetes.io/name=health-api -n production
kubectl get events -n production --sort-by='.lastTimestamp'
```

### Database connection issues

```bash
# Verify Cloud SQL is running
gcloud sql instances describe health-api-db --format='value(state)'

# Verify secrets exist
gcloud secrets versions access latest --secret=db-host
gcloud secrets versions access latest --secret=db-name

# Check pod environment
kubectl exec -it deploy/health-api -n production -- env | grep DB_
```

### Image pull errors

```bash
gcloud artifacts repositories describe health-api-repo --location=us-central1
```

## Infrastructure Management

### Terraform

```bash
cd terraform
terraform plan    # Review changes
terraform apply   # Apply changes
terraform output  # View outputs
```

### Teardown

```bash
# Remove Helm releases
helm uninstall health-api -n staging
helm uninstall health-api -n production

# Destroy infrastructure
cd terraform
terraform destroy
```
