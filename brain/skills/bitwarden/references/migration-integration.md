# Migration and Integration Patterns

Guide for migrating between Bitwarden tools and integrating with development workflows.

## Migration from Personal Vault to Secrets Manager

### Planning the Migration

**Assess your current vault:**
```bash
# List all items by type
bw list items | jq 'group_by(.type) | map({type: .[0].type, count: length})'

# Find API keys and secrets (in notes)
bw list items | jq '.[] | select(.notes != null and (.notes | test("api|key|secret|token"; "i"))) | {name, id, notes: (.notes | .[0:100])}'

# Find items with custom fields
bw list items | jq '.[] | select(.fields != null) | {name, fields: .fields}'
```

**Categorize secrets:**
- Personal development secrets → Keep in personal vault
- Team/shared secrets → Move to Secrets Manager
- Production secrets → Move to Secrets Manager
- Environment-specific → Create separate projects

### Migration Scripts

**Extract secrets from personal vault:**
```bash
#!/bin/bash
# extract-secrets.sh

# Unlock vault
export BW_SESSION=$(bw unlock --raw)

# Extract API keys from secure notes
bw list items --search "api" | jq -r '.[] | 
  select(.type == 2) | 
  "Item: \(.name)\nNotes: \(.notes)\n---"' > api-keys-export.txt

# Extract custom fields that look like secrets
bw list items | jq -r '.[] | 
  select(.fields != null) | 
  .fields[] | 
  select(.name | test("api|key|secret|token"; "i")) | 
  "Field: \(.name)\nValue: \(.value)\nItem: \(parent.name)\n---"' > custom-fields-export.txt
```

**Batch import to Secrets Manager:**
```bash
#!/bin/bash
# batch-import.sh

PROJECT_ID="your-project-id"

# Import common development secrets
bws secret create "GITHUB_TOKEN" "$(bw get notes 'GitHub API')" --project-id "$PROJECT_ID"
bws secret create "OPENAI_API_KEY" "$(bw get notes 'OpenAI API')" --project-id "$PROJECT_ID"
bws secret create "STRIPE_SECRET_KEY" "$(bw get item 'Stripe' | jq -r '.fields[] | select(.name=="Secret Key") | .value')" --project-id "$PROJECT_ID"

echo "Migration complete"
```

## CI/CD Integration Patterns

### GitHub Actions

**.github/workflows/deploy.yml:**
```yaml
name: Deploy
on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      # Install BWS CLI
      - name: Install BWS
        run: npm install -g @bitwarden/sdk
        
      # Deploy with secrets
      - name: Deploy with secrets
        env:
          BWS_ACCESS_TOKEN: ${{ secrets.BWS_ACCESS_TOKEN }}
        run: |
          bws run --project-id ${{ secrets.BWS_PROJECT_ID }} -- ./deploy.sh
```

### Docker Compose

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  app:
    image: myapp
    environment:
      # These will be injected by bws run
      - DATABASE_URL
      - API_KEY
      - REDIS_URL
    command: bws run --project-id ${BWS_PROJECT_ID} -- npm start
```

**Run with secrets:**
```bash
export BWS_ACCESS_TOKEN="your-token"
export BWS_PROJECT_ID="project-id"
docker-compose up
```

### Local Development

**Development setup script:**
```bash
#!/bin/bash
# dev-setup.sh

echo "Setting up development environment..."

# Check if BWS is configured
if [ -z "$BWS_ACCESS_TOKEN" ]; then
    echo "BWS_ACCESS_TOKEN not set"
    echo "Get your token from: https://vault.bitwarden.com"
    exit 1
fi

# Start development with secrets
echo "Starting development server with secrets..."
bws run --project-id "$DEV_PROJECT_ID" -- npm run dev
```

## Environment Management

### Project Structure
```
Production Project
├── DATABASE_URL
├── API_KEYS (Stripe, GitHub, etc.)
├── OAUTH_SECRETS
└── ENCRYPTION_KEYS

Development Project  
├── DEV_DATABASE_URL
├── TEST_API_KEYS
├── LOCAL_SECRETS
└── DEBUG_TOKENS

Staging Project
├── STAGING_DATABASE_URL
├── STAGING_API_KEYS
└── STAGING_SECRETS
```

### Environment Switching
```bash
#!/bin/bash
# env-switch.sh

case "$1" in
    "dev")
        export BWS_PROJECT_ID="dev-project-id"
        ;;
    "staging") 
        export BWS_PROJECT_ID="staging-project-id"
        ;;
    "prod")
        export BWS_PROJECT_ID="prod-project-id"
        ;;
    *)
        echo "Usage: $0 {dev|staging|prod}"
        exit 1
        ;;
esac

echo "Switched to $1 environment"
bws run -- "$2"
```

## Team Onboarding

### New Developer Setup

**onboard-developer.sh:**
```bash
#!/bin/bash
# Team onboarding script

DEVELOPER_EMAIL="$1"
PROJECT_NAME="$2"

echo "Onboarding $DEVELOPER_EMAIL to $PROJECT_NAME"

# 1. Invite to Bitwarden organization (manual step)
echo "Manual step: Invite $DEVELOPER_EMAIL to Bitwarden org"

# 2. Create development access token (manual step)
echo "Manual step: Create access token for $DEVELOPER_EMAIL"

# 3. Provide setup instructions
cat > developer-setup.md << EOF
# Developer Setup

1. Install BWS CLI:
   \`npm install -g @bitwarden/sdk\`

2. Set your access token:
   \`export BWS_ACCESS_TOKEN="your-token-here"\`

3. Test connection:
   \`bws project list\`

4. Run development:
   \`./scripts/dev-with-secrets.sh\`
EOF

echo "Setup instructions created in developer-setup.md"
```

### Secret Rotation

**rotate-secrets.sh:**
```bash
#!/bin/bash
# Secret rotation script

PROJECT_ID="$1"
SECRET_NAME="$2"
NEW_VALUE="$3"

if [ -z "$3" ]; then
    echo "Usage: $0 <project-id> <secret-name> <new-value>"
    exit 1
fi

# Get current secret ID
SECRET_ID=$(bws secret list --project-id "$PROJECT_ID" | jq -r ".[] | select(.key == \"$SECRET_NAME\") | .id")

if [ -z "$SECRET_ID" ]; then
    echo "Secret not found: $SECRET_NAME"
    exit 1
fi

# Update secret
bws secret edit "$SECRET_ID" --value "$NEW_VALUE"
echo "Rotated secret: $SECRET_NAME"

# Log rotation (optional)
echo "$(date): Rotated $SECRET_NAME" >> secret-rotation.log
```

## Integration with Other Tools

### Terraform

**variables.tf:**
```hcl
variable "database_password" {
  description = "Database password from Bitwarden"
  type        = string
  sensitive   = true
}
```

**Run Terraform with secrets:**
```bash
bws run --project-id "$INFRA_PROJECT" -- terraform apply \
  -var="database_password=$DATABASE_PASSWORD"
```

### Ansible

**playbook.yml:**
```yaml
- name: Deploy application
  hosts: webservers
  environment:
    DATABASE_URL: "{{ lookup('env', 'DATABASE_URL') }}"
    API_KEY: "{{ lookup('env', 'API_KEY') }}"
  tasks:
    - name: Deploy app
      # Tasks here have access to secrets as env vars
```

**Run Ansible with secrets:**
```bash
bws run --project-id "$DEPLOY_PROJECT" -- ansible-playbook playbook.yml
```

### Kubernetes

**secret-injector.yaml:**
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: secret-sync
spec:
  template:
    spec:
      containers:
      - name: secret-sync
        image: bitwarden/bws
        env:
        - name: BWS_ACCESS_TOKEN
          valueFrom:
            secretKeyRef:
              name: bws-token
              key: token
        command:
        - /bin/sh
        - -c
        - |
          # Sync secrets from BWS to k8s secrets
          kubectl create secret generic app-secrets \
            --from-literal=database-url="$(bws secret get $DB_SECRET_ID | jq -r '.value')" \
            --from-literal=api-key="$(bws secret get $API_SECRET_ID | jq -r '.value')"
```

## Backup and Disaster Recovery

### Export Secrets Manager Secrets
```bash
#!/bin/bash
# backup-secrets.sh

PROJECT_ID="$1"
BACKUP_DIR="backup-$(date +%Y%m%d)"

mkdir -p "$BACKUP_DIR"

# Export project metadata
bws project get "$PROJECT_ID" > "$BACKUP_DIR/project.json"

# Export all secrets (encrypted with GPG)
bws secret list --project-id "$PROJECT_ID" > "$BACKUP_DIR/secrets-list.json"

# Export individual secret values (be very careful with this)
for secret_id in $(bws secret list --project-id "$PROJECT_ID" | jq -r '.[].id'); do
    secret_name=$(bws secret get "$secret_id" | jq -r '.key')
    bws secret get "$secret_id" | gpg --cipher-algo AES256 --compress-algo 1 --s2k-mode 3 --s2k-digest-algo SHA512 --s2k-count 65536 --force-mdc --encrypt -r "$GPG_RECIPIENT" > "$BACKUP_DIR/${secret_name}.gpg"
done

echo "Backup complete in $BACKUP_DIR"
```

### Restore from Backup
```bash
#!/bin/bash
# restore-secrets.sh

BACKUP_DIR="$1" 
NEW_PROJECT_ID="$2"

for encrypted_file in "$BACKUP_DIR"/*.gpg; do
    secret_name=$(basename "$encrypted_file" .gpg)
    secret_value=$(gpg --decrypt "$encrypted_file")
    bws secret create "$secret_name" "$secret_value" --project-id "$NEW_PROJECT_ID"
done

echo "Restore complete to project $NEW_PROJECT_ID"
```