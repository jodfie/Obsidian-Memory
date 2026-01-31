# Creating Bitwarden Items

Complete guide for creating different types of items in Bitwarden personal vault using the `bw` CLI.

## Item Types

- **Type 1**: Login (username/password)
- **Type 2**: Secure Note
- **Type 3**: Card
- **Type 4**: Identity

## Login Items (Type 1)

### Basic Login
```bash
echo '{
  "type": 1,
  "name": "GitHub",
  "login": {
    "username": "myusername",
    "password": "mypassword"
  }
}' | bw encode | bw create item
```

### Login with URL
```bash
echo '{
  "type": 1,
  "name": "Gmail",
  "login": {
    "username": "user@gmail.com",
    "password": "securepassword",
    "uris": [
      {
        "match": null,
        "uri": "https://mail.google.com"
      }
    ]
  }
}' | bw encode | bw create item
```

### Login with Multiple URLs
```bash
echo '{
  "type": 1,
  "name": "AWS Console",
  "login": {
    "username": "admin",
    "password": "password123",
    "uris": [
      {
        "match": null,
        "uri": "https://console.aws.amazon.com"
      },
      {
        "match": null,
        "uri": "https://signin.aws.amazon.com"
      }
    ]
  }
}' | bw encode | bw create item
```

### Login with TOTP
```bash
echo '{
  "type": 1,
  "name": "GitHub 2FA",
  "login": {
    "username": "myusername",
    "password": "mypassword",
    "totp": "otpauth://totp/GitHub:user?secret=SECRETKEY&issuer=GitHub"
  }
}' | bw encode | bw create item
```

### Login in Specific Folder
```bash
# First, get folder ID
bw list folders | jq -r '.[] | "\(.id) | \(.name)"'

# Create item in folder
echo '{
  "type": 1,
  "name": "Work Database",
  "login": {
    "username": "dbuser",
    "password": "dbpass"
  },
  "folderId": "folder-id-here"
}' | bw encode | bw create item
```

## Secure Notes (Type 2)

### Basic Note
```bash
echo '{
  "type": 2,
  "name": "API Keys",
  "secureNote": {
    "type": 0
  },
  "notes": "GitHub API: ghp_abc123\nStripe API: sk_live_xyz789"
}' | bw encode | bw create item
```

### Note with Custom Fields
```bash
echo '{
  "type": 2,
  "name": "Server Config",
  "secureNote": {
    "type": 0
  },
  "notes": "Production server configuration",
  "fields": [
    {
      "name": "Server IP",
      "value": "192.168.1.100",
      "type": 0
    },
    {
      "name": "SSH Port",
      "value": "2222",
      "type": 0
    },
    {
      "name": "SSH Key",
      "value": "-----BEGIN PRIVATE KEY-----\n...",
      "type": 1
    }
  ]
}' | bw encode | bw create item
```

## Cards (Type 3)

### Credit Card
```bash
echo '{
  "type": 3,
  "name": "Personal Credit Card",
  "card": {
    "cardholderName": "John Doe",
    "number": "4111111111111111",
    "expiryMonth": "12",
    "expiryYear": "2025",
    "code": "123"
  }
}' | bw encode | bw create item
```

## Identity (Type 4)

### Personal Identity
```bash
echo '{
  "type": 4,
  "name": "Personal Identity",
  "identity": {
    "title": "Mr",
    "firstName": "John",
    "lastName": "Doe",
    "email": "john.doe@example.com",
    "phone": "555-1234",
    "address1": "123 Main St",
    "city": "Anytown",
    "state": "CA",
    "postalCode": "90210",
    "country": "US"
  }
}' | bw encode | bw create item
```

## Common Patterns

### API Key Storage
Store API keys as secure notes with structured format:
```bash
echo '{
  "type": 2,
  "name": "Development API Keys",
  "secureNote": {
    "type": 0
  },
  "notes": "Collection of development API keys",
  "fields": [
    {
      "name": "GitHub Token",
      "value": "ghp_abc123...",
      "type": 1
    },
    {
      "name": "Stripe Test Key",
      "value": "sk_test_xyz789...",
      "type": 1
    },
    {
      "name": "OpenAI API",
      "value": "sk-proj-abc123...",
      "type": 1
    }
  ]
}' | bw encode | bw create item
```

### Database Credentials
```bash
echo '{
  "type": 1,
  "name": "Production Database",
  "login": {
    "username": "app_user",
    "password": "secure_db_password"
  },
  "fields": [
    {
      "name": "Host",
      "value": "db.example.com",
      "type": 0
    },
    {
      "name": "Port",
      "value": "5432",
      "type": 0
    },
    {
      "name": "Database",
      "value": "production_app",
      "type": 0
    },
    {
      "name": "Connection String",
      "value": "postgresql://app_user:password@db.example.com:5432/production_app",
      "type": 1
    }
  ]
}' | bw encode | bw create item
```

### SSH Key Storage
```bash
echo '{
  "type": 2,
  "name": "Production Server SSH",
  "secureNote": {
    "type": 0
  },
  "notes": "SSH access to production servers",
  "fields": [
    {
      "name": "Private Key",
      "value": "-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----",
      "type": 1
    },
    {
      "name": "Public Key",
      "value": "ssh-rsa AAAAB3NzaC1yc2E...",
      "type": 0
    },
    {
      "name": "Server",
      "value": "prod.example.com",
      "type": 0
    },
    {
      "name": "Username",
      "value": "deploy",
      "type": 0
    }
  ]
}' | bw encode | bw create item
```

## Field Types

- **Type 0**: Text (visible)
- **Type 1**: Hidden (password-like)
- **Type 2**: Boolean

## URI Match Types

- `null`: Default (exact match)
- `0`: Base domain
- `1`: Host
- `2`: Starts with
- `3`: Exact
- `4`: Regular expression
- `5`: Never

## Tips

1. **Use templates**: Save common JSON templates as files for reuse
2. **Validate JSON**: Use `jq '.'` to validate JSON before encoding
3. **Batch create**: Script multiple item creation for team setups
4. **Custom fields**: Use for structured data that doesn't fit standard fields
5. **Folders**: Organize with folders for different environments (dev/staging/prod)