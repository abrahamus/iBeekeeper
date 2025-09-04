# 🆓 iBeekeeper Render.com Deployment Guide

## Why Render.com?
- ✅ **100% FREE** (no credit card required initially)
- ✅ **PostgreSQL database** included free
- ✅ **SSL certificates** automatic
- ✅ **GitHub integration** - auto-deploys on push
- ✅ **No sleeping** issues like some free tiers
- ✅ **Custom domains** supported

## Prerequisites
- GitHub account with your iBeekeeper repository
- Render.com account (free)

## Step-by-Step Deployment

### 1. Prepare Your Repository
Your repo is already configured! ✅
- `requirements.txt` - ✅ Ready
- `Procfile` - ✅ Updated for Flask app factory

### 2. Create Render Account
1. Go to https://render.com
2. Sign up with GitHub (no credit card needed)
3. Authorize Render to access your repositories

### 3. Deploy Web Service

#### A. Create Web Service
1. **Dashboard** → **New** → **Web Service**
2. **Connect your iBeekeeper repository**
3. **Configure the service:**

```yaml
Name: ibeekeeper (or your preferred name)
Environment: Python 3
Region: Oregon (US-West) or your preferred region
Branch: main (or your main branch)
Build Command: pip install -r requirements.txt
Start Command: gunicorn "app:create_app()" --bind 0.0.0.0:$PORT
```

#### B. Configure Environment Variables
In the **Environment** section, add:

```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=fdccdd2d7a83151d15ffb199005306b2545b2775984a77c3003f8d092eeee9e3

# Session Security
SESSION_COOKIE_SECURE=True

# File Uploads
UPLOAD_FOLDER=/opt/render/project/src/uploads

# Database URL (will be set automatically when you create database)
# DATABASE_URL=postgresql://... (added after database creation)
```

### 4. Create PostgreSQL Database

#### A. Add Database Service
1. **Dashboard** → **New** → **PostgreSQL**
2. **Configure:**
```yaml
Name: ibeekeeper-db
Database: ibeekeeper
User: ibeekeeper_user
Region: Same as your web service
PostgreSQL Version: 15 (latest)
```

#### B. Connect Database to Web Service
1. Go to your **Web Service** → **Environment**
2. Add variable:
```bash
DATABASE_URL=<your-postgres-connection-string-from-database-dashboard>
```

*Note: Copy the "External Database URL" from your PostgreSQL dashboard*

### 5. Deploy!
1. Click **Create Web Service**
2. Render will automatically:
   - Build your application
   - Install dependencies
   - Start your Flask app
   - Provide HTTPS URL

## Configuration Files

### Update Procfile for Render
Your current Procfile works perfectly:
```
web: gunicorn "app:create_app()"
```

But for Render, let's make it more explicit:

```
web: gunicorn "app:create_app()" --bind 0.0.0.0:$PORT
```

### Optional: render.yaml (Infrastructure as Code)
Create `render.yaml` for automated setup:

```yaml
services:
  - type: web
    name: ibeekeeper
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn "app:create_app()" --bind 0.0.0.0:$PORT
    envVars:
      - key: FLASK_ENV
        value: production
      - key: SECRET_KEY
        value: fdccdd2d7a83151d15ffb199005306b2545b2775984a77c3003f8d092eeee9e3
      - key: SESSION_COOKIE_SECURE
        value: true
      - key: UPLOAD_FOLDER
        value: /opt/render/project/src/uploads
      - key: DATABASE_URL
        fromDatabase:
          name: ibeekeeper-db
          property: connectionString

databases:
  - name: ibeekeeper-db
    databaseName: ibeekeeper
    user: ibeekeeper_user
```

## Free Tier Limits

### Web Service (Free)
- ✅ **750 hours/month** of runtime
- ✅ **512 MB RAM**
- ✅ **0.1 CPU**
- ✅ **Automatic SSL**
- ⚠️ **Spins down after 15min inactivity** (spins back up on request)

### PostgreSQL (Free)
- ✅ **90 days free** (then $7/month)
- ✅ **1 GB storage**
- ✅ **100 connections**
- ✅ **Daily backups**

## Post-Deployment Steps

### 1. Verify Deployment
1. Check **Logs** in Render dashboard
2. Visit your app URL (https://your-app-name.onrender.com)
3. Test registration/login

### 2. Create Admin User
Once deployed, you can create admin user through the web interface or via Render Shell:

1. **Web Service** → **Shell**
2. Run:
```python
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

### 3. Test Core Features
- ✅ User registration/login
- ✅ Transaction management
- ✅ File uploads
- ✅ Reports generation

## Custom Domain (Optional)
1. **Web Service** → **Settings** → **Custom Domains**
2. Add your domain
3. Update DNS records as instructed
4. SSL certificate automatically provisioned

## Monitoring & Maintenance

### Built-in Monitoring
- **Logs**: Real-time in dashboard
- **Metrics**: CPU, memory, response times
- **Health checks**: Automatic

### Keep App Alive (Optional)
To prevent sleeping, you can:
1. Use a free uptime monitor (UptimeRobot)
2. Ping your app every 14 minutes
3. Or upgrade to paid tier ($7/month for always-on)

## Cost Breakdown

### Completely Free Option
- **Web Service**: Free (with sleeping after 15min)
- **Database**: Free for 90 days, then need alternative
- **SSL & Domain**: Free
- **Total**: $0/month for 90 days

### Long-term Affordable Option  
- **Web Service**: $7/month (always-on)
- **Database**: $7/month (persistent)
- **Total**: $14/month (still cheaper than Railway)

## Alternative Free Database Options

If you want completely free long-term:

### 1. **SQLite** (Simplest)
Update your config to use SQLite for free hosting:
```python
DATABASE_URL=sqlite:///ibeekeeper.db
```

### 2. **Supabase** (PostgreSQL)
- Free PostgreSQL hosting
- 500MB storage
- Connect via DATABASE_URL

### 3. **PlanetScale** (MySQL)
- Free MySQL hosting
- 1GB storage
- Generous free tier

## Troubleshooting

### Common Issues

1. **App won't start**
```bash
# Check logs for missing environment variables
# Ensure all dependencies are in requirements.txt
```

2. **Database connection fails**
```bash
# Verify DATABASE_URL is correctly set
# Check database service is running
```

3. **File uploads don't work**
```python
# Render filesystem is ephemeral
# Consider using cloud storage (AWS S3, Cloudinary) for production
```

## Success! 🎉

Your iBeekeeper app will be available at:
`https://your-app-name.onrender.com`

Features working:
- 🐝 Beautiful iOS/macOS UI
- 🔐 Secure authentication  
- 📊 Transaction management
- 📁 File handling
- 📱 Mobile-responsive
- 🌙 Dark mode support

## Need Help?
- **Render Docs**: https://render.com/docs
- **Render Community**: https://community.render.com
- **Support**: Available via dashboard

**Your iBeekeeper app is ready for free deployment on Render! 🚀**