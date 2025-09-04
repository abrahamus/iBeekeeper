# 🚁 iBeekeeper Fly.io Deployment Guide

## Why Fly.io?
- ✅ **Generous FREE tier** - no credit card initially
- ✅ **Always-on apps** (no sleeping)
- ✅ **Global deployment** with edge locations
- ✅ **PostgreSQL included** (3GB free)
- ✅ **Great performance**
- ✅ **Production-ready** platform

## Free Tier Limits
- **3 shared-cpu-1x VMs** (256MB RAM each)
- **3GB PostgreSQL storage**
- **160GB/month bandwidth**
- **No sleeping** - apps stay running!

## Prerequisites
- GitHub repository with iBeekeeper
- Fly.io account (free)
- Fly CLI installed

## Step-by-Step Deployment

### 1. Install Fly CLI

#### macOS:
```bash
brew install flyctl
```

#### Linux/WSL:
```bash
curl -L https://fly.io/install.sh | sh
```

#### Windows:
```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

### 2. Login to Fly.io
```bash
fly auth signup  # Create account
# OR
fly auth login   # If you have account
```

### 3. Initialize Your App
In your iBeekeeper directory:

```bash
cd /path/to/your/iBeekeeper
fly launch
```

**During setup:**
- **App name**: Choose a unique name (e.g., `ibeekeeper-yourname`)
- **Region**: Choose closest to your users
- **Add PostgreSQL?**: **YES** ✅
- **Add Redis?**: **NO**
- **Deploy now?**: **NO** (we'll configure first)

### 4. Configure Your App

Fly created `fly.toml`. Update it:

```toml
app = "your-app-name"
primary_region = "sea"  # or your chosen region

[build]
  builder = "paket/builder:base"

[env]
  FLASK_ENV = "production"
  SESSION_COOKIE_SECURE = "true"
  UPLOAD_FOLDER = "/app/uploads"

[[services]]
  http_checks = []
  internal_port = 8080
  processes = ["app"]
  protocol = "tcp"
  script_checks = []
  [services.concurrency]
    hard_limit = 25
    soft_limit = 20
    type = "connections"

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [services.tcp_checks]
    grace_period = "1s"
    interval = "15s"
    restart_limit = 0
    timeout = "2s"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false  # Keep running (important!)
  auto_start_machines = true
  min_machines_running = 1    # Always keep 1 running

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 256
```

### 5. Create Dockerfile
Create `Dockerfile` in your project root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads/users

# Expose port
EXPOSE 8080

# Start command
CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:8080", "--workers", "1"]
```

### 6. Set Environment Variables

Set your secret key and other sensitive vars:

```bash
fly secrets set SECRET_KEY=fdccdd2d7a83151d15ffb199005306b2545b2775984a77c3003f8d092eeee9e3

# Database URL is automatically set by Fly when you add PostgreSQL
```

### 7. Deploy Your App

```bash
fly deploy
```

Fly will:
- Build your Docker image
- Deploy to your chosen region
- Set up PostgreSQL database
- Provide HTTPS URL

### 8. Check Your Deployment

```bash
# View app status
fly status

# Check logs
fly logs

# Open your app
fly open
```

## Database Management

### Connect to Database
```bash
# Get database connection info
fly postgres connect -a your-app-name-db

# Or get connection string
fly postgres db list -a your-app-name-db
```

### Create Admin User
```bash
# Connect to your app console
fly ssh console

# Then run:
python3 -c "
from app import create_app
from models.user import User
from models import db

app = create_app()
with app.app_context():
    admin = User(
        email='admin@ibeekeeper.com',
        first_name='Admin',
        last_name='User'
    )
    admin.set_password('admin123')
    admin.is_active = True
    db.session.add(admin)
    db.session.commit()
    print('Admin user created!')
"
```

## File Storage Considerations

Fly.io has **ephemeral storage** - files are lost on restarts. For production, consider:

### Option 1: Use Cloud Storage
Update your app to use AWS S3, Cloudinary, or similar.

### Option 2: Fly.io Volumes (Persistent Storage)
```bash
# Create volume (additional cost - $0.15/GB/month)
fly volumes create ibeekeeper_data --size 10

# Update fly.toml to mount volume
[mounts]
  source = "ibeekeeper_data"
  destination = "/app/uploads"
```

## Custom Domain

### Add Custom Domain
```bash
fly domains add yourdomain.com
fly domains add www.yourdomain.com
```

### Configure DNS
Point your domain to Fly.io:
```
A record: yourdomain.com → [Fly IP from domains command]
CNAME: www.yourdomain.com → yourdomain.com
```

SSL certificates are automatically provided!

## Scaling (Optional)

### Scale Memory/CPU
```bash
# Upgrade VM (uses more of free tier)
fly scale memory 512  # 512MB RAM

# Add more machines
fly scale count 2     # Run 2 instances
```

### Scale Database
```bash
# Upgrade PostgreSQL storage
fly postgres create --name myapp-db --vm-size shared-cpu-1x --volume-size 10
```

## Monitoring & Logs

### Real-time Monitoring
```bash
# Live logs
fly logs -f

# App metrics
fly status --all

# Machine status
fly machine list
```

### Health Checks
Fly automatically monitors your app and restarts if needed.

## Cost Management

### Stay Within Free Tier
```bash
# Check usage
fly dashboard billing

# Monitor resource usage
fly status --all
```

### Free Tier Optimization
- Use 1 shared-cpu-1x machine (256MB)
- PostgreSQL stays within 3GB
- Optimize your app for low memory usage

## Troubleshooting

### App Won't Start
```bash
# Check build logs
fly logs

# Common fixes:
# 1. Ensure Dockerfile is correct
# 2. Check environment variables
# 3. Verify database connection
```

### Database Issues
```bash
# Reset database (if needed)
fly postgres create --name your-app-db-new

# Update DATABASE_URL
fly secrets set DATABASE_URL=postgresql://...
```

### Performance Issues
```bash
# Scale up memory
fly scale memory 512

# Check resource usage
fly status --all
```

## Success! 🎉

Your iBeekeeper will be available at:
- `https://your-app-name.fly.dev`
- Plus your custom domain (if configured)

**Benefits of Fly.io:**
- ✅ **No sleeping** - app stays responsive
- ✅ **Global deployment** - fast worldwide
- ✅ **Production-ready** - used by major companies
- ✅ **Great free tier** - generous limits
- ✅ **Easy scaling** - when you need it

## Advanced Features

### Multiple Regions
```bash
# Add regions for global deployment
fly regions add lax sea fra
```

### Monitoring
```bash
# Set up monitoring
fly monitoring setup
```

### Automated Deployments
Set up GitHub Actions for CI/CD:

```yaml
# .github/workflows/fly.yml
name: Fly Deploy
on: [push]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: superfly/flyctl-actions/setup-flyctl@master
    - run: flyctl deploy --remote-only
      env:
        FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

**Your iBeekeeper app is ready for free, always-on deployment on Fly.io! 🚁**